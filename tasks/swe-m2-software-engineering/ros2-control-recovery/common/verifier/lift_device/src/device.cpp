#include <algorithm>
#include <bit>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

#include "hardware_interface/system_interface.hpp"
#include "pluginlib/class_list_macros.hpp"

namespace lift_device
{
constexpr double no_value = std::numeric_limits<double>::quiet_NaN();
constexpr std::size_t observations = 13;
const std::array<std::string, observations> channels = {
  "left/position", "left/velocity", "right/position", "right/velocity",
  "feedback/strain", "feedback/goal", "feedback/goal_velocity",
  "feedback/epoch", "feedback/healthy", "feedback/required_epoch",
  "feedback/weight_left", "feedback/weight_right", "feedback/sample"};

template<std::size_t Count>
class SharedSlot
{
  using Words = std::array<std::uint64_t, Count + 1>;
public:
  ~SharedSlot()
  {
    if (address_)
      munmap(address_, sizeof(Words));
  }

  void open_file(const std::string& path, bool writing)
  {
    const int fd = open(path.c_str(), writing ? O_RDWR : O_RDONLY);
    if (fd < 0)
      throw std::runtime_error("transport open");
    void* result = mmap(nullptr, sizeof(Words), writing ? PROT_READ | PROT_WRITE : PROT_READ,
        MAP_SHARED, fd, 0);
    close(fd);
    if (result == MAP_FAILED)
      throw std::runtime_error("transport mapping");
    address_ = static_cast<Words*>(result);
  }

  bool get(std::array<double, Count>& row)
  {
    auto sequence = std::atomic_ref<std::uint64_t>((*address_)[0]);
    const auto first = sequence.load(std::memory_order_acquire);
    if (!first || first & 1)
      return false;
    for (std::size_t i = 0; i < Count; ++i)
      row[i] = std::bit_cast<double>(std::atomic_ref<std::uint64_t>((*address_)[i + 1])
        .load(std::memory_order_relaxed));
    std::atomic_thread_fence(std::memory_order_acquire);
    return first == sequence.load(std::memory_order_relaxed);
  }

  void set(const std::array<double, Count>& row)
  {
    auto seq = std::atomic_ref<std::uint64_t>((*address_)[0]);
    const auto start = seq.load(std::memory_order_relaxed) + 1;
    seq.store(start, std::memory_order_seq_cst);
    for (std::size_t i = 0; i < Count; ++i)
      std::atomic_ref<std::uint64_t>((*address_)[i + 1])
        .store(std::bit_cast<std::uint64_t>(row[i]), std::memory_order_relaxed);
    seq.store(start + 1, std::memory_order_release);
  }

private:
  Words* address_ = nullptr;
};

class PairDevice final : public hardware_interface::SystemInterface
{
  using CallbackReturn = hardware_interface::CallbackReturn;
  using Return = hardware_interface::return_type;
public:
  CallbackReturn on_init(const hardware_interface::HardwareComponentInterfaceParams& params) override
  {
    if (SystemInterface::on_init(params) != CallbackReturn::SUCCESS)
      return CallbackReturn::ERROR;
    try {
      sensors_.open_file(get_hardware_info().hardware_parameters.at("sensor_path"), false);
      drives_.open_file(get_hardware_info().hardware_parameters.at("effort_path"), true);
    } catch (const std::exception&) {
      return CallbackReturn::ERROR;
    }
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn on_configure(const rclcpp_lifecycle::State&) override
  {
    for (std::size_t i = 0; i < channels.size(); ++i)
      state_[i] = get_state_interface_handle(channels[i]);
    forces_[0] = get_command_interface_handle("left/effort");
    forces_[1] = get_command_interface_handle("right/effort");
    return CallbackReturn::SUCCESS;
  }

  Return read(const rclcpp::Time&, const rclcpp::Duration&) override
  {
    std::array<double, observations> row;
    if (sensors_.get(row))
      for (std::size_t i = 0; i < row.size(); ++i)
        set_state(state_[i], row[i], false);
    return Return::OK;
  }

  Return write(const rclcpp::Time&, const rclcpp::Duration&) override
  {
    std::array<double, 2> output{no_value, no_value};
    for (std::size_t i = 0; i < output.size(); ++i)
      get_command(forces_[i], output[i], false);
    drives_.set(output);
    return Return::OK;
  }

private:
  SharedSlot<observations> sensors_;
  SharedSlot<2> drives_;
  std::array<hardware_interface::StateInterface::SharedPtr, observations> state_{};
  std::array<hardware_interface::CommandInterface::SharedPtr, 2> forces_{};
};

}

PLUGINLIB_EXPORT_CLASS(lift_device::PairDevice, hardware_interface::SystemInterface)
