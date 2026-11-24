#include <rmf_traffic/DetectConflict.hpp>
#include <rmf_traffic/agv/Interpolate.hpp>
#include <rmf_traffic/geometry/Circle.hpp>
#include <rmf_traffic/schedule/Database.hpp>
#include <rmf_traffic/schedule/Mirror.hpp>
#include <rmf_traffic/schedule/Negotiation.hpp>

#include <algorithm>
#include <array>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <tuple>
#include <vector>

namespace rt = rmf_traffic;
namespace sc = rmf_traffic::schedule;
using Ns = std::int64_t;
using Pose = Eigen::Vector3d;
using Times = std::array<Ns, 2>;

rt::Time at(Ns value) { return rt::Time{} + std::chrono::nanoseconds(value); }
Ns ns(rt::Time time)
{
  return std::chrono::duration_cast<std::chrono::nanoseconds>(time.time_since_epoch()).count();
}

struct Platform
{
  rt::Profile profile;
  rt::Profile cautious;
  rt::agv::VehicleTraits traits;
  Pose home, stage, exit;
};

struct Cabin
{
  Ns ride;
  std::array<Pose, 2> door;
};

struct Site
{
  std::string map;
  Ns slot, horizon, carrier_observation, lift_observation;
  std::array<Platform, 2> courier;
  Platform carrier;
  Times deadline;
  std::vector<Ns> carrier_departures;
  std::vector<Cabin> cabins;
  std::vector<std::vector<Times>> windows;
};

struct Move
{
  Ns start, end;
};

struct Dock
{
  std::size_t cabin;
  Move move;
  Ns board, delivery;
};

using Docks = std::array<Dock, 2>;

struct Suffix
{
  std::array<Move, 2> crossing;
  std::vector<Docks> docks;
  std::array<rt::Trajectory, 2> routes;
};

struct Policy
{
  std::array<Move, 2> approach;
  std::vector<Suffix> suffix;
};

Pose read_pose()
{
  Pose input;
  std::cin >> input[0] >> input[1] >> input[2];
  return input;
}

rt::Profile profile(double radius)
{
  return rt::Profile(rt::geometry::make_final_convex<rt::geometry::Circle>(radius));
}

Platform read_platform()
{
  double radius, velocity, acceleration, angular_velocity, angular_acceleration;
  std::cin >> radius >> velocity >> acceleration >> angular_velocity >> angular_acceleration;
  auto nominal = profile(radius);
  return {nominal, profile(radius + .004),
    rt::agv::VehicleTraits({velocity, acceleration}, {angular_velocity, angular_acceleration}, nominal),
    read_pose(), read_pose(), read_pose()};
}

Site read_site()
{
  std::string map;
  Ns slot, horizon, first, second;
  std::cin >> std::quoted(map) >> slot >> horizon >> first >> second;
  Site site{map, slot, horizon, first, second,
    {read_platform(), read_platform()}, read_platform(), {}, {}, {}, {}};
  std::cin >> site.deadline[0] >> site.deadline[1];
  std::size_t branches, cabins, lift_states;
  std::cin >> branches >> cabins >> lift_states;
  if (branches < 1 || branches > 8 || cabins < 1 || cabins > 8 || lift_states < 1 || lift_states > 8)
    throw std::runtime_error("scenario exceeds native planner bounds");
  site.carrier_departures.resize(branches);
  for (auto& departure : site.carrier_departures)
    std::cin >> departure;
  for (std::size_t i = 0; i < cabins; ++i)
  {
    Ns ride;
    std::cin >> ride;
    site.cabins.push_back({ride, {read_pose(), read_pose()}});
  }
  site.windows.resize(lift_states, std::vector<Times>(cabins));
  for (auto& window : site.windows)
    for (auto& boarding : window)
      std::cin >> boarding[0] >> boarding[1];
  if (!std::cin)
    throw std::runtime_error("invalid native site stream");
  return site;
}

Ns next_slot(Ns input, Ns slot)
{
  return input / slot * slot + (input % slot ? slot : 0);
}

Ns append(rt::Trajectory& path, const Platform& robot, Ns start, const Pose& first, const Pose& last)
{
  const auto move = rt::agv::Interpolate::positions(robot.traits, at(start), {first, last});
  for (const auto& waypoint : move)
    path.insert(waypoint);
  return ns(move.back().time());
}

rt::Trajectory occupied(rt::Trajectory path, Ns horizon)
{
  if (ns(path.back().time()) < horizon)
    path.insert(at(horizon), path.back().position(), Pose::Zero());
  return path;
}

bool clear(const Platform& a, const rt::Trajectory& x, const Platform& b, const rt::Trajectory& y)
{
  return !rt::DetectConflict::between(a.cautious, x, nullptr, b.cautious, y, nullptr);
}

struct DockMove
{
  Dock authority;
  rt::Trajectory trajectory;
};

std::vector<DockMove> dock_moves(const Site& site, const Suffix& common,
  const Times& boarding, std::size_t cabin, std::size_t courier, const rt::Trajectory& carrier)
{
  const auto& robot = site.courier[courier];
  const auto& lift = site.cabins[cabin];
  const Ns board = boarding[courier], delivery = board + lift.ride;
  std::vector<DockMove> options;
  if (delivery > site.deadline[courier])
    return options;
  const Ns earliest = next_slot(std::max(site.lift_observation, common.crossing[courier].end),
    site.slot);
  for (Ns start = earliest; start <= board; start += site.slot)
  {
    auto path = common.routes[courier];
    const Ns end = append(path, robot, start, robot.exit, lift.door[courier]);
    if (end > board)
      break;
    auto hold = occupied(std::move(path), site.horizon);
    if (clear(robot, hold, site.carrier, carrier))
      options.push_back({{cabin, {start, end}, board, delivery}, std::move(hold)});
  }
  return options;
}

std::optional<Docks> choose_docks(const Site& site, const Suffix& common,
  const std::vector<Times>& options, const rt::Trajectory& carrier)
{
  std::optional<Docks> best;
  std::array<std::vector<std::vector<DockMove>>, 2> by_cabin;
  for (std::size_t courier = 0; courier < 2; ++courier)
    for (std::size_t cabin = 0; cabin < site.cabins.size(); ++cabin)
      by_cabin[courier].push_back(dock_moves(site,common,options[cabin],cabin,courier,carrier));

  for (std::size_t a = 0; a < site.cabins.size(); ++a)
    for (std::size_t b = 0; b < site.cabins.size(); ++b)
    {
      for (const auto& first : by_cabin[0][a])
      {
        for (const auto& second : by_cabin[1][b])
        {
          Docks proposal{first.authority, second.authority};
          if (a == b && proposal[0].board < proposal[1].delivery
            && proposal[1].board < proposal[0].delivery)
            continue;
          const auto key = [](const Docks& docks) { return std::make_pair(docks[0].delivery, docks[1].delivery); };
          if (best && key(proposal) >= key(*best))
            continue;
          if (clear(site.courier[0],first.trajectory,site.courier[1],second.trajectory))
            best = proposal;
        }
      }
    }
  return best;
}

sc::Itinerary itinerary(const std::string& map, const rt::Trajectory& path)
{
  return {rt::Route(map, path)};
}

bool native_agreement(const Site& site, const Suffix& solution, const rt::Trajectory& path,
  const std::array<rt::Trajectory, 2>& approach)
{
  using Desc = sc::ParticipantDescription;
  sc::Database database;
  const Desc ad("courier-a", "delivery", Desc::Rx::Responsive, site.courier[0].profile);
  const Desc bd("courier-b", "delivery", Desc::Rx::Responsive, site.courier[1].profile);
  const Desc cd("carrier", "external", Desc::Rx::Unresponsive, site.carrier.profile);
  const auto a = database.register_participant(ad), b = database.register_participant(bd);
  const auto c = database.register_participant(cd);
  database.set(a.id(), a.last_plan_id() + 1, itinerary(site.map, approach[0]),
    a.next_storage_base(), a.last_itinerary_version() + 1);
  database.set(b.id(), b.last_plan_id() + 1, itinerary(site.map, approach[1]),
    b.next_storage_base(), b.last_itinerary_version() + 1);
  database.set(c.id(), c.last_plan_id() + 1, itinerary(site.map, path),
    c.next_storage_base(), c.last_itinerary_version() + 1);
  sc::Mirror mirror;
  mirror.update_participants_info({{a.id(), ad}, {b.id(), bd}, {c.id(), cd}});
  if (!mirror.update(database.changes(sc::query_all(), std::nullopt)))
    return false;
  auto negotiation = sc::Negotiation::make_shared(mirror.snapshot(), {a.id(), b.id()});
  if (!negotiation)
    return false;
  auto initial = negotiation->table(std::vector<rt::ParticipantId>{a.id()});
  if (!initial || !initial->submit(a.last_plan_id() + 2, itinerary(site.map, solution.routes[0]), 1))
    return false;
  auto response = negotiation->table(std::vector<rt::ParticipantId>{a.id(), b.id()});
  if (!response || !response->submit(b.last_plan_id() + 2, itinerary(site.map, solution.routes[1]), 1))
    return false;
  const auto selected = negotiation->evaluate(sc::QuickestFinishEvaluator{});
  return negotiation->ready() && selected && selected->proposal().size() == 2;
}

std::optional<Suffix> choose_crossing(const Site& site, Ns departure,
  const std::array<rt::Trajectory, 2>& approach)
{
  rt::Trajectory carrier;
  const Ns prefix_end = append(carrier, site.carrier, 0, site.carrier.home, site.carrier.stage);
  if (departure < prefix_end)
    throw std::runtime_error("carrier departure overlaps committed prefix");
  append(carrier, site.carrier, departure, site.carrier.stage, site.carrier.exit);
  const auto carrier_hold = occupied(carrier, site.horizon);
  const Ns first = next_slot(site.carrier_observation, site.slot);
  for (Ns a = first; a <= site.deadline[0]; a += site.slot)
  {
    auto ta = approach[0];
    const Ns ae = append(ta, site.courier[0], a, site.courier[0].stage, site.courier[0].exit);
    if (ae >= site.deadline[0])
      break;
    if (!clear(site.courier[0], ta, site.carrier, carrier_hold))
      continue;
    for (Ns b = first; b <= site.deadline[1]; b += site.slot)
    {
      auto tb = approach[1];
      const Ns be = append(tb, site.courier[1], b, site.courier[1].stage, site.courier[1].exit);
      if (be >= site.deadline[1])
        break;
      Suffix possibility{{Move{a, ae}, Move{b, be}}, {}, {ta, tb}};
      if (!clear(site.courier[1], tb, site.carrier, carrier_hold)
        || !clear(site.courier[0], ta, site.courier[1], tb))
        continue;
      for (const auto& lift : site.windows)
      {
        const auto result = choose_docks(site, possibility, lift, carrier_hold);
        if (!result)
          break;
        possibility.docks.push_back(*result);
      }
      if (possibility.docks.size() == site.windows.size() &&
        native_agreement(site, possibility, carrier, approach))
        return possibility;
    }
  }
  return std::nullopt;
}

std::optional<Policy> plan(const Site& site)
{
  for (Ns a = 0; a <= site.carrier_observation; a += site.slot)
    for (Ns b = 0; b <= site.carrier_observation; b += site.slot)
    {
      const Times starts{a, b};
      Policy root;
      std::array<rt::Trajectory, 2> approach;
      bool in_time = true;
      for (std::size_t i = 0; i < 2; ++i)
      {
        const auto& robot = site.courier[i];
        approach[i].insert(at(0), robot.home, Pose::Zero());
        const Ns end = append(approach[i], robot, starts[i], robot.home, robot.stage);
        root.approach[i] = {starts[i], end};
        in_time &= end <= site.carrier_observation;
      }
      if (!in_time)
        continue;
      for (const Ns departure : site.carrier_departures)
      {
        auto suffix = choose_crossing(site, departure, approach);
        if (!suffix)
          break;
        root.suffix.push_back(std::move(*suffix));
      }
      if (root.suffix.size() == site.carrier_departures.size())
        return root;
    }
  return std::nullopt;
}

void write_moves(const std::array<Move, 2>& moves)
{
  for (const auto& move : moves)
    std::cout << move.start << ' ' << move.end << '\n';
}

int main()
{
  try
  {
    const auto policy = plan(read_site());
    if (!policy)
    {
      std::cout << "blocked\n";
      return 0;
    }
    std::cout << "ready\n";
    write_moves(policy->approach);
    for (const auto& suffix : policy->suffix)
    {
      write_moves(suffix.crossing);
      for (const auto& docks : suffix.docks)
        for (const auto& dock : docks)
          std::cout << dock.cabin << ' ' << dock.move.start << ' ' << dock.move.end << ' ' <<
            dock.board << ' ' << dock.delivery << '\n';
    }
  }
  catch (const std::exception& error)
  {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
