// Small stdin adapter over released native Jazzy traffic geometry.
#include <rmf_traffic/DetectConflict.hpp>
#include <rmf_traffic/agv/Interpolate.hpp>
#include <rmf_traffic/agv/VehicleTraits.hpp>
#include <rmf_traffic/geometry/Circle.hpp>
#include <rmf_traffic/schedule/Database.hpp>
#include <rmf_traffic/schedule/Mirror.hpp>
#include <rmf_traffic/schedule/Query.hpp>

#include <chrono>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

namespace rt = rmf_traffic;

rt::Profile footprint(double radius)
{
  if (!(radius > 0.0))
    throw std::runtime_error("invalid robot radius");
  return rt::Profile(rt::geometry::make_final_convex<rt::geometry::Circle>(radius));
}

std::vector<Eigen::Vector3d> poses(std::size_t count)
{
  if (count < 2 || count > 400)
    throw std::runtime_error("invalid pose count");
  std::vector<Eigen::Vector3d> result;
  for (std::size_t i = 0; i < count; ++i)
  {
    Eigen::Vector3d row;
    if (!(std::cin >> row.x() >> row.y() >> row.z()))
      throw std::runtime_error("incomplete pose stream");
    result.push_back(row);
  }
  return result;
}

void interpolate()
{
  double radius, v, a, w, alpha;
  std::size_t n;
  if (!(std::cin >> radius >> v >> a >> w >> alpha >> n))
    throw std::runtime_error("expected vehicle traits and waypoint count");
  const rt::agv::VehicleTraits vehicle({v, a}, {w, alpha}, footprint(radius));
  auto trajectory = rt::agv::Interpolate::positions(vehicle, rt::Time{}, poses(n), rt::agv::Interpolate::Options(true));
  std::cout << trajectory.size() << '\n' << std::setprecision(17);
  for (const auto& row : trajectory)
    std::cout << std::chrono::duration_cast<std::chrono::nanoseconds>(
      row.time().time_since_epoch()).count() << ' ' << row.position().transpose()
      << ' ' << row.velocity().transpose() << '\n';
}

struct InputRoute
{
  double radius;
  rt::Route route;
};

InputRoute route()
{
  std::string map;
  double radius;
  std::size_t count;
  if (!(std::cin >> map >> radius >> count) || count < 2 || count > 10000)
    throw std::runtime_error("expected map, footprint and timed route count");
  rt::Trajectory trajectory;
  for (std::size_t i = 0; i < count; ++i)
  {
    std::int64_t ns;
    Eigen::Vector3d p, v;
    if (!(std::cin >> ns >> p.x() >> p.y() >> p.z() >> v.x() >> v.y() >> v.z()))
      throw std::runtime_error("incomplete timed route");
    trajectory.insert(rt::Time{} + std::chrono::nanoseconds(ns), p, v);
  }
  return {radius, rt::Route(map, std::move(trajectory))};
}

std::optional<rt::DetectConflict::Conflict> collision_at(const InputRoute& a, const InputRoute& b)
{
  return a.route.map() == b.route.map()
    ? rt::DetectConflict::between(footprint(a.radius),a.route.trajectory(),nullptr,
      footprint(b.radius),b.route.trajectory(),nullptr)
    : std::nullopt;
}

void print_conflict(const std::optional<rt::DetectConflict::Conflict>& collision)
{
  if (collision)
    std::cout << std::chrono::duration_cast<std::chrono::nanoseconds>(
      collision->time.time_since_epoch()).count() << '\n';
  else
    std::cout << "clear\n";
}

void schedule()
{
  namespace sc = rt::schedule;
  std::int64_t delay, observed, release;
  if (!(std::cin >> delay >> observed >> release))
    throw std::runtime_error("expected itinerary delay, observed checkpoint and release checkpoint");
  const auto a = route();
  const auto b = route();
  const sc::ParticipantDescription carrier("carrier", "vendor", sc::ParticipantDescription::Rx::Unresponsive, footprint(a.radius));
  const sc::ParticipantDescription courier("courier", "dispatch", sc::ParticipantDescription::Rx::Responsive, footprint(b.radius));
  sc::Database database;
  const auto A = database.register_participant(carrier);
  const auto B = database.register_participant(courier);
  const auto pa = A.last_plan_id()+1;
  const auto v = A.last_itinerary_version()+1;
  database.set(A.id(), pa, {a.route}, A.next_storage_base(), v);
  database.set(B.id(), B.last_plan_id()+1, {b.route}, B.next_storage_base(), B.last_itinerary_version()+1);
  sc::Mirror mirror;
  const auto query = sc::query_all();
  mirror.update_participants_info({{A.id(),carrier},{B.id(),courier}});
  if (!mirror.update(database.changes(query,std::nullopt)))
    throw std::runtime_error("could not initialize native schedule mirror");
  if (delay != 0)
  {
    database.delay(A.id(), std::chrono::nanoseconds(delay), v+1);
    if (!mirror.update(database.changes(query,mirror.latest_version())))
      throw std::runtime_error("could not apply native itinerary delay");
  }
  bool ready = false;
  if (observed >= 0 && release >= 0)
  {
    auto watcher = mirror.watch_dependency({A.id(),pa,0,static_cast<rt::CheckpointId>(release)},
      [&ready]{ready = true;}, []{});
    database.reached(A.id(),pa,{static_cast<rt::CheckpointId>(observed)},1);
    if (!mirror.update(database.changes(query,mirror.latest_version())))
      throw std::runtime_error("could not mirror native progress");
  }
  const auto a_view = mirror.get_itinerary(A.id());
  const auto b_view = mirror.get_itinerary(B.id());
  if (!a_view || !b_view || a_view->size() != 1 || b_view->size() != 1)
    throw std::runtime_error("native mirror lost an itinerary");
  print_conflict(collision_at({a.radius,*a_view->front()},{b.radius,*b_view->front()}));
  std::cout << (ready ? "ready" : "blocked") << '\n';
}

int main(int argc, char** argv)
{
  try
  {
    if (argc != 2)
      throw std::runtime_error("usage: rmf-native interpolate|conflict|schedule");
    const std::string cmd = argv[1];
    if (cmd == "interpolate")
      interpolate();
    else if (cmd == "conflict")
    {
      const auto a = route();
      const auto b = route();
      print_conflict(collision_at(a,b));
    }
    else if (cmd == "schedule")
      schedule();
    else
      throw std::runtime_error("unknown native operation");
  }
  catch (const std::exception& e)
  {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
