#include <rmf_traffic/DetectConflict.hpp>
#include <rmf_traffic/agv/Interpolate.hpp>
#include <rmf_traffic/geometry/Circle.hpp>
#include <rmf_traffic/schedule/Database.hpp>
#include <rmf_traffic/schedule/Mirror.hpp>
#include <rmf_traffic/schedule/Negotiation.hpp>

#include <algorithm>
#include <array>
#include <iomanip>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <tuple>

namespace rt = rmf_traffic;
namespace sc = rmf_traffic::schedule;
using Ns = int64_t;
using V = Eigen::Vector3d;
using Id = rt::ParticipantId;

rt::Time time_at(Ns nanos)
{
  return rt::Time{} + std::chrono::nanoseconds(nanos);
}

Ns ns(rt::Time time)
{
  return std::chrono::duration_cast<std::chrono::nanoseconds>(time.time_since_epoch()).count();
}

struct Platform
{
  rt::Profile profile;
  rt::agv::VehicleTraits traits;
  V home, stage, goal;
};

struct Job
{
  Ns ready, deadline;
  int priority;
  bool staged;
};

struct Guard
{
  int axis, sign;
  double coordinate;
};

struct Leg
{
  int from, to;
  Ns start, end;
};

struct Motion
{
  rt::Trajectory trajectory;
  rt::Trajectory occupied;
  std::vector<Leg> legs;
};

struct Choice
{
  std::array<Motion, 2> motions;
};

struct Request
{
  std::string map;
  bool protected_mode;
  Ns now, slot, horizon, carrier_departure;
  std::array<Platform, 3> users;
  std::array<Job, 2> jobs;
  std::array<Guard, 2> guards;
};

V read_pose()
{
  V pose;
  std::cin >> pose[0] >> pose[1] >> pose[2];
  return pose;
}

Platform read_platform()
{
  double radius, linear, acceleration, angular, angular_acceleration;
  std::cin >> radius >> linear >> acceleration >> angular >> angular_acceleration;
  auto shape = rt::geometry::make_final_convex<rt::geometry::Circle>(radius);
  rt::Profile profile(shape);
  rt::agv::VehicleTraits traits({linear, acceleration}, {angular, angular_acceleration}, profile);
  auto home = read_pose(), stage = read_pose(), goal = read_pose();
  return {profile, traits, home, stage, goal};
}

Job read_job()
{
  Job job;
  std::cin >> job.ready >> job.deadline >> job.priority >> job.staged;
  return job;
}

Guard read_guard()
{
  Guard guard;
  std::cin >> guard.axis >> guard.sign >> guard.coordinate;
  return guard;
}

Request read_request()
{
  std::string map;
  bool protect;
  Ns now, slot, horizon, departure;
  std::cin >> std::quoted(map) >> protect >> now >> slot >> horizon >> departure;
  Request request{map, protect, now, slot, horizon, departure,
    {read_platform(), read_platform(), read_platform()},
    {read_job(), read_job()}, {read_guard(), read_guard()}};
  if (!std::cin)
    throw std::runtime_error("invalid native negotiation request");
  return request;
}

void append(rt::Trajectory& target, const rt::Trajectory& source)
{
  for (const auto& waypoint : source)
    target.insert(waypoint);
}

rt::Trajectory interpolate(const Platform& platform, Ns start, const V& from, const V& to)
{
  return rt::agv::Interpolate::positions(platform.traits, time_at(start), {from, to});
}

Ns append_leg(rt::Trajectory& target, const Platform& platform, Ns start, const V& from, const V& to)
{
  const auto trajectory = interpolate(platform, start, from, to);
  append(target, trajectory);
  return ns(trajectory.back().time());
}

rt::Trajectory occupied(const rt::Trajectory& trajectory, Ns horizon)
{
  auto result = trajectory;
  if (ns(result.back().time()) < horizon)
    result.insert(time_at(horizon), result.back().position(), V::Zero());
  return result;
}

Motion direct(const Platform& platform, Ns start, Ns horizon)
{
  rt::Trajectory trajectory;
  trajectory.insert(time_at(0), platform.home, V::Zero());
  const Ns end = append_leg(trajectory, platform, start, platform.home, platform.goal);
  return {trajectory, occupied(trajectory, horizon), {{0, 2, start, end}}};
}

std::optional<Motion> staged(const Platform& platform, Ns approach, Ns gate, Ns horizon)
{
  rt::Trajectory trajectory;
  trajectory.insert(time_at(0), platform.home, V::Zero());
  const Ns arrival = append_leg(trajectory, platform, approach, platform.home, platform.stage);
  if (arrival > gate)
    return std::nullopt;
  const Ns end = append_leg(trajectory, platform, gate, platform.stage, platform.goal);
  return Motion{trajectory, occupied(trajectory, horizon), {{0, 1, approach, arrival}, {1, 2, gate, end}}};
}

rt::Trajectory carrier(const Request& request)
{
  const auto& platform = request.users[2];
  auto trajectory = interpolate(platform, 0, platform.home, platform.stage);
  if (ns(trajectory.back().time()) > request.carrier_departure)
    throw std::runtime_error("carrier departure overlaps the committed prefix");
  append_leg(trajectory, platform, request.carrier_departure, platform.stage, platform.goal);
  return trajectory;
}

bool clear(const Platform& a, const rt::Trajectory& first, const Platform& b, const rt::Trajectory& second)
{
  return !rt::DetectConflict::between(a.profile, first, nullptr, b.profile, second, nullptr);
}

std::optional<Ns> guard_time(const rt::Trajectory& trajectory, const Guard& guard)
{
  for (const auto& waypoint : trajectory)
    if (guard.sign * (waypoint.position()[guard.axis] - guard.coordinate) >= 0)
      return ns(waypoint.time());
  return std::nullopt;
}

Ns next_slot(Ns time, Ns slot)
{
  return time / slot * slot + (time % slot ? slot : 0);
}

using Rank = std::tuple<Ns, Ns, Ns, Ns>;

Rank cost(const Choice& choice, std::size_t first)
{
  const auto& high = choice.motions[first].legs;
  const auto& low = choice.motions[1 - first].legs;
  return {high.back().end, low.back().end, high.front().start, low.front().start};
}

std::array<std::optional<Choice>, 2> search(
  const Request& r, const rt::Trajectory& carrier_route)
{
  const std::size_t staged_index = r.jobs[0].staged ? 0 : 1;
  const std::size_t direct_index = 1 - staged_index;
  const auto& a = r.users[staged_index];
  const auto& b = r.users[direct_index];
  const auto& c = r.users[2];
  const auto c_hold = occupied(carrier_route, r.horizon);
  const auto& aj = r.jobs[staged_index];
  const auto& bj = r.jobs[direct_index];
  std::array<std::optional<Choice>, 2> best;
  const auto c_clear = guard_time(carrier_route, r.guards[1]);
  if (r.protected_mode && !c_clear)
    return best;
  const Ns earliest_a = next_slot(std::max(aj.ready, r.now), r.slot);
  const Ns earliest_b = next_slot(std::max(bj.ready, r.now), r.slot);
  for (Ns b_start = earliest_b; b_start <= bj.deadline; b_start += r.slot)
  {
    const auto bt = direct(b, b_start, r.horizon);
    if (bt.legs.back().end > bj.deadline)
      break;
    if (!clear(b, bt.occupied, c, c_hold))
      continue;
    const auto b_clear = guard_time(bt.trajectory, r.guards[0]);
    if (r.protected_mode && !b_clear)
      continue;
    for (Ns a_start = earliest_a; a_start <= aj.deadline; a_start += r.slot)
    {
      if (!r.protected_mode)
      {
        auto at = direct(a, a_start, r.horizon);
        if (at.legs.back().end > aj.deadline)
          break;
        if (clear(a, at.occupied, c, c_hold) && clear(a, at.occupied, b, bt.occupied))
        {
          Choice choice;
          choice.motions[staged_index] = std::move(at);
          choice.motions[direct_index] = bt;
          for (std::size_t i = 0; i < 2; ++i)
            if (!best[i] || cost(choice, i) < cost(*best[i], i))
              best[i] = choice;
        }
        continue;
      }
      const Ns a_stage = ns(interpolate(a, a_start, a.home, a.stage).back().time());
      const Ns first_gate = next_slot(std::max({a_stage, *b_clear, *c_clear}), r.slot);
      for (Ns gate = first_gate; gate <= aj.deadline; gate += r.slot)
      {
        auto at = staged(a, a_start, gate, r.horizon);
        if (!at || at->legs.back().end > aj.deadline)
          break;
        if (clear(a, at->occupied, c, c_hold) && clear(a, at->occupied, b, bt.occupied))
        {
          Choice choice;
          choice.motions[staged_index] = std::move(*at);
          choice.motions[direct_index] = bt;
          for (std::size_t i = 0; i < 2; ++i)
            if (!best[i] || cost(choice, i) < cost(*best[i], i))
              best[i] = choice;
          break;
        }
      }
    }
  }
  return best;
}

sc::Itinerary itinerary(const std::string& map, const rt::Trajectory& trajectory)
{
  rt::Route route(map, trajectory);
  for (std::size_t i = 0; i < trajectory.size(); ++i)
    route.checkpoints().insert(i);
  return {std::move(route)};
}

class Priority : public sc::Negotiation::Evaluator
{
public:
  Priority(Id first, Id second) : ordered_{first, second} {}

  std::size_t choose(const std::vector<const sc::Negotiation::Proposal*>& choices) const override
  {
    const auto rank = [this](const auto& proposal)
    {
      std::array<Ns, 2> end{};
      for (const auto& submission : proposal)
        for (std::size_t i = 0; i < ordered_.size(); ++i)
          if (submission.participant == ordered_[i])
            end[i] = ns(submission.itinerary.at(0).trajectory().back().time());
      return end;
    };
    return std::distance(choices.begin(), std::min_element(choices.begin(), choices.end(),
      [&](const auto* a, const auto* b) { return rank(*a) < rank(*b); }));
  }

private:
  std::array<Id, 2> ordered_;
};

std::size_t negotiate(const Request& request, const rt::Trajectory& carrier_route,
  const std::array<std::optional<Choice>, 2>& alternatives)
{
  using Desc = sc::ParticipantDescription;
  const auto describe = [&](std::size_t i)
  {
    return Desc(std::to_string(i), "responsive-fleet", Desc::Rx::Responsive, request.users[i].profile);
  };
  const auto ad = describe(0), bd = describe(1), cd = describe(2);
  sc::Database db;
  const auto a = db.register_participant(ad), b = db.register_participant(bd),
    c = db.register_participant(cd);
  const std::array<Id, 2> ids{a.id(), b.id()};
  const std::array<rt::PlanId, 2> plans{a.last_plan_id() + 1, b.last_plan_id() + 1};
  const auto cp = c.last_plan_id() + 1;
  auto committed = itinerary(request.map, carrier_route);
  db.set(c.id(), cp, committed, c.next_storage_base(), c.last_itinerary_version() + 1);
  sc::Mirror mirror;
  mirror.update_participants_info({{a.id(), ad}, {b.id(), bd}, {c.id(), cd}});
  if (!mirror.update(db.changes(sc::query_all(), std::nullopt)))
    throw std::runtime_error("native snapshot was rejected");
  auto round = sc::Negotiation::make_shared(mirror.snapshot(), {a.id(), b.id(), c.id()});
  if (!round)
    throw std::runtime_error("native negotiation could not start");
  for (std::size_t i = 0; i < 2; ++i)
  {
    if (!alternatives[i])
      continue;
    const auto& motion = alternatives[i]->motions;
    const auto first = round->table(std::vector<Id>{ids[i]});
    const auto other = 1 - i;
    if (!first->submit(plans[i], itinerary(request.map, motion[i].trajectory), 1))
      throw std::runtime_error("native starting proposal was rejected");
    const auto response = round->table(std::vector<Id>{ids[i], ids[other]});
    if (!response || !response->submit(plans[other], itinerary(request.map, motion[other].trajectory), 1))
      throw std::runtime_error("native responsive proposal was rejected");
    const auto carrier_response = round->table(std::vector<Id>{ids[i], ids[other], c.id()});
    if (!carrier_response || !carrier_response->submit(cp, committed, 1))
      throw std::runtime_error("native committed itinerary was rejected");
  }
  const std::size_t first = request.jobs[1].priority > request.jobs[0].priority ? 1 : 0;
  const auto proposal = round->evaluate(Priority(ids[first], ids[1 - first]));
  if (!round->ready() || !proposal || proposal->proposal().size() != 3)
    throw std::runtime_error("native negotiation did not reach agreement");
  return proposal->proposal().front().participant == a.id() ? 0 : 1;
}

void write_trajectory(const rt::Trajectory& trajectory)
{
  std::cout << trajectory.size() << '\n';
  for (const auto& waypoint : trajectory)
    std::cout << ns(waypoint.time()) << ' ' << waypoint.position()[0] << ' '
      << waypoint.position()[1] << ' ' << waypoint.position()[2] << '\n';
}

int main()
{
  try
  {
    const auto command = read_request();
    const auto c = carrier(command);
    const auto alternatives = search(command, c);
    if (!alternatives[0] && !alternatives[1])
    {
      std::cout << "blocked\n";
      return 0;
    }
    const auto choice = negotiate(command, c, alternatives);
    std::cout << std::setprecision(17) << "ready\n";
    for (const auto& motion : alternatives[choice]->motions)
    {
      std::cout << motion.legs.size() << '\n';
      for (const auto& leg : motion.legs)
        std::cout << leg.from << ' ' << leg.to << ' ' << leg.start << ' ' << leg.end << '\n';
      write_trajectory(motion.trajectory);
    }
    write_trajectory(c);
  }
  catch (const std::exception& error)
  {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
