#include <rmf_traffic/DetectConflict.hpp>
#include <rmf_traffic/agv/Interpolate.hpp>
#include <rmf_traffic/agv/VehicleTraits.hpp>
#include <rmf_traffic/geometry/Circle.hpp>
#include <rmf_traffic/schedule/Database.hpp>
#include <rmf_traffic/schedule/Mirror.hpp>
#include <rmf_traffic/schedule/Negotiation.hpp>
#include <rmf_traffic/schedule/Query.hpp>

#include <chrono>
#include <iostream>
#include <memory>
#include <stdexcept>

namespace rt = rmf_traffic;
namespace sc = rmf_traffic::schedule;
using namespace std::chrono_literals;

void verify(bool condition, const char* message)
{
  if (!condition)
    throw std::runtime_error(message);
}

rt::Route route(int start, const Eigen::Vector3d& begin, const Eigen::Vector3d& finish)
{
  rt::Trajectory trajectory;
  const auto v = (finish - begin) / 8.0;
  trajectory.insert(rt::Time{} + std::chrono::seconds(start), begin, v);
  trajectory.insert(rt::Time{} + std::chrono::seconds(start + 8), finish, v);
  return rt::Route("office-L1", std::move(trajectory));
}

const rt::Route& itinerary(const sc::ItineraryViewer& viewer, rt::ParticipantId participant)
{
  const auto routes = viewer.get_itinerary(participant);
  verify(routes && routes->size() == 1, "one native route expected");
  return *routes->at(0);
}

std::optional<rt::DetectConflict::Conflict> collision(
    const rt::Profile& first, const rt::Route& a,
    const rt::Profile& second, const rt::Route& b)
{
  if (a.map() != b.map())
    return std::nullopt;
  return rt::DetectConflict::between(
      first, a.trajectory(), nullptr, second, b.trajectory(), nullptr);
}

int main()
{
  const rt::Profile carrier(rt::geometry::make_final_convex<rt::geometry::Circle>(0.38));
  const rt::Profile courier(rt::geometry::make_final_convex<rt::geometry::Circle>(0.31));
  const sc::ParticipantDescription A(
      "slow-carrier", "read-only-fleet", sc::ParticipantDescription::Rx::Unresponsive, carrier);
  const sc::ParticipantDescription B(
      "courier", "full-control-fleet", sc::ParticipantDescription::Rx::Responsive, courier);
  auto db = std::make_shared<sc::Database>();
  const auto a = db->register_participant(A);
  const auto b = db->register_participant(B);
  const auto va = a.last_itinerary_version() + 1;
  const auto vb = b.last_itinerary_version() + 1;
  const auto pa = a.last_plan_id() + 1;
  const auto pb = b.last_plan_id() + 1;
  db->set(a.id(), pa, {route(0, {-3, 0, 0}, {3, 0, 0})}, a.next_storage_base(), va);
  db->set(b.id(), pb, {route(9, {0, -3, 0}, {0, 3, 0})}, b.next_storage_base(), vb);

  const auto query = sc::query_all();
  sc::Mirror mirror;
  mirror.update_participants_info({{a.id(), A}, {b.id(), B}});
  verify(mirror.update(db->changes(query, std::nullopt)), "initial schedule patch");
  const auto old_version = mirror.latest_version().value();
  verify(!collision(carrier, itinerary(*db, a.id()), courier, itinerary(*db, b.id())),
      "initial crossing is time-separated");
  std::cout << "initial_no_conflict mirror_version=" << old_version << '\n';

  db->delay(a.id(), 9s, va + 1);
  const auto skipped = db->latest_version();
  db->delay(a.id(), 1s, va + 2);
  const auto conflict = collision(carrier, itinerary(*db, a.id()), courier, itinerary(*db, b.id()));
  verify(conflict.has_value(), "late carrier must conflict with courier");
  const auto native_conflict_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
      conflict->time.time_since_epoch()).count();
  verify(!collision(carrier, itinerary(mirror, a.id()), courier, itinerary(mirror, b.id())),
      "stale mirror still shows the old conflict-free schedule");
  verify(!mirror.update(db->changes(query, skipped)), "delta based on missing version must be rejected");
  verify(mirror.latest_version() == old_version, "rejected delta must leave mirror unchanged");
  verify(mirror.update(db->changes(query, old_version)), "catch-up from actual mirror cursor");
  verify(collision(carrier, itinerary(mirror, a.id()), courier, itinerary(mirror, b.id())).has_value(),
      "restored mirror must perceive the actual conflict");
  std::cout << "delay_plus_10s native_conflict_ms=" << native_conflict_ms
            << " rejected_gap_base=" << skipped << " restored_version=" << *mirror.latest_version() << '\n';

  auto negotiation = sc::Negotiation::make_shared(db->snapshot(), {a.id(), b.id()});
  verify(negotiation != nullptr, "native negotiation construction");
  auto unresponsive = negotiation->table(a.id(), {});
  const auto unchanged = itinerary(*db, a.id());
  verify(unresponsive->submit(pa, {unchanged}, unresponsive->version()+1),
      "keep read-only carrier's known trajectory in the negotiation");
  auto response = negotiation->table(b.id(), {a.id()});
  auto detour = route(20, {0, -3, 0}, {0, 3, 0});
  verify(!collision(carrier, unchanged, courier, detour),
      "candidate response independently verified against carrier");
  const auto attempt_version = response->version() + 1;
  verify(response->submit(pb+1, {detour}, attempt_version), "submit safe alternative");
  verify(!response->submit(pb+2, {itinerary(*db, b.id())}, attempt_version),
      "duplicate proposal version cannot replace committed attempt");
  response->forfeit(attempt_version-1);
  verify(negotiation->ready(), "stale cancellation cannot remove newer proposal");
  const auto selected = negotiation->evaluate(sc::QuickestFinishEvaluator{});
  verify(selected && selected->proposal().size()==2, "native negotiated solution");
  verify(selected->proposal().at(1).plan==pb+1, "selected proposal retains safe plan");
  const auto winner_conflict = collision(
      carrier, selected->proposal().at(0).itinerary.at(0),
      courier, selected->proposal().at(1).itinerary.at(0));
  verify(!winner_conflict, "both native winning trajectories must be compatible");
  db->set(b.id(), pb+1, {detour}, b.next_storage_base()+1, vb+1);
  std::cout << "negotiation selected_safe_plan=" << pb+1
            << " stale_proposal_and_forfeit_ignored=1\n";

  // A native checkpoint is a trajectory waypoint, not a vendor path index.
  const rt::agv::VehicleTraits traits({0.65, 0.35}, {0.65, 0.35}, carrier);
  const std::vector<Eigen::Vector3d> vendor_path = {
      {-3, 0, 0}, {0, 0, 0}, {3, 1, 0}};
  const auto expanded = rt::agv::Interpolate::positions(traits, rt::Time{}+25s, vendor_path);
  verify(expanded.size() > vendor_path.size(), "native route generates additional checkpoints");

  int old_plan_deprecated = 0;
  int invalid_release = 0;
  auto old_wait = db->watch_dependency({a.id(), pa, 0, 1},
    [&] { ++invalid_release; }, [&] { ++old_plan_deprecated; });
  db->set(a.id(), pa+1, {rt::Route("office-L1", expanded)}, a.next_storage_base()+1, va+3);
  verify(old_wait.deprecated() && !old_wait.reached() && old_plan_deprecated == 1,
      "old dependency must be replaced when a native itinerary changes");
  const auto release_checkpoint = expanded.size()-1;
  const auto mirror_before_progress = mirror.latest_version();
  verify(mirror.update(db->changes(query, mirror_before_progress)), "apply replacement plan before subscribing");
  int released = 0;
  int deprecated = 0;
  auto ready = mirror.watch_dependency({a.id(), pa+1, 0, release_checkpoint},
      [&] { ++released; }, [&] { ++deprecated; });
  db->reached(a.id(), pa, {release_checkpoint}, 91);
  db->reached(a.id(), pa+1, {1}, 1);
  verify(mirror.update(db->changes(query, mirror.latest_version())), "apply earlier progress");
  verify(!ready.finished() && !released && !invalid_release && !deprecated,
      "old-plan progress and early checkpoint must not release courier");
  db->reached(a.id(), pa+1, {release_checkpoint}, 2);
  verify(mirror.update(db->changes(query, mirror.latest_version())), "apply exact current progress");
  verify(ready.reached() && !ready.deprecated() && released==1 && !invalid_release,
      "only exact active plan and native checkpoint can release the wait");
  std::cout << "vendor_points=" << vendor_path.size() << " native_checkpoints=" << expanded.size()
            << " waited_for_checkpoint=" << release_checkpoint
            << " early_or_old_released=0 final_releases=" << released << '\n';
}
