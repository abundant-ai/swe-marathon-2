#include "device_slot.hpp"

#include <array>
#include <atomic>
#include <charconv>
#include <cmath>
#include <limits>
#include <string>
#include <vector>

#include "hardware_interface/system_interface.hpp"
#include "pluginlib/class_list_macros.hpp"

namespace fenced_drive
{
using hardware_interface::CallbackReturn;
using hardware_interface::return_type;

/// One native Jazzy hardware component backed by generation-fenced device slots.
class FencedSystem final : public hardware_interface::SystemInterface
{
public:
  CallbackReturn on_init(const hardware_interface::HardwareComponentInterfaceParams & params) override
  {
    if (SystemInterface::on_init(params) != CallbackReturn::SUCCESS) {
      return CallbackReturn::ERROR;
    }
    try {
      const auto & info = get_hardware_info();
      if (info.joints.size() != 1) {
        return CallbackReturn::ERROR;
      }
      prefix_ = info.joints.at(0).name + "/";
      device_path_ = info.hardware_parameters.at("device_file");
      command_path_ = info.hardware_parameters.at("command_file");
      const auto & age = info.hardware_parameters.at("max_sample_age_ns");
      const auto parsed = std::from_chars(age.data(), age.data() + age.size(), maximum_age_);
      if (parsed.ec != std::errc() || parsed.ptr != age.data() + age.size() || maximum_age_ == 0) {
        return CallbackReturn::ERROR;
      }
    } catch (const std::exception &) {
      return CallbackReturn::ERROR;
    }
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn on_configure(const rclcpp_lifecycle::State &) override
  {
    try {
      for (std::size_t i = 0; i < states_.size(); ++i) {
        states_[i] = get_state_interface_handle(prefix_ + state_keys_[i]);
      }
      for (std::size_t i = 0; i < commands_.size(); ++i) {
        commands_[i] = get_command_interface_handle(prefix_ + state_keys_[i == 0 ? 0 : 2]);
      }
      device_.map(device_path_, false);
      command_.map(command_path_, true);
    } catch (const std::exception &) {
      return CallbackReturn::ERROR;
    }
    inhibit();
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn on_activate(const rclcpp_lifecycle::State &) override
  {
    active_.store(true, std::memory_order_release);
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn on_deactivate(const rclcpp_lifecycle::State &) override
  {
    active_.store(false, std::memory_order_release);
    claim_.store(0, std::memory_order_release);
    prepared_.store(0, std::memory_order_release);
    inhibit();
    return CallbackReturn::SUCCESS;
  }

  CallbackReturn on_shutdown(const rclcpp_lifecycle::State & previous) override
  {
    return on_deactivate(previous);
  }

  return_type read(const rclcpp::Time &, const rclcpp::Duration &) override
  {
    const auto sample = capture();
    if (sample && sample->healthy) {
      for (std::size_t i = 0; i < sample->values.size(); ++i) {
        set_state(states_[i], sample->values[i], false);
      }
    }
    set_state(states_[3], static_cast<double>(observed_generation_.load(std::memory_order_relaxed)), false);
    set_state(states_[4], sample && sample->healthy ? 1.0 : 0.0, false);
    const auto authority = claim_.load(std::memory_order_acquire) == 0 ? 0 : claimed_generation_.load(std::memory_order_relaxed);
    set_state(states_[5], static_cast<double>(authority), false);
    return return_type::OK;
  }

  return_type write(const rclcpp::Time &, const rclcpp::Duration &) override
  {
    const auto sample = capture();
    const auto mode = claim_.load(std::memory_order_acquire);
    double output = 0.0;
    if (active_.load(std::memory_order_acquire) && mode != 0 && sample && sample->healthy &&
        sample->generation == claimed_generation_.load(std::memory_order_relaxed) &&
        get_command(commands_[mode - 1], output, false) && std::isfinite(output)) {
      command_.publish({0, sample->generation, monotonic_ns(), mode,
                        std::bit_cast<std::uint64_t>(output), sample->sequence, 0, 0});
    } else {
      inhibit();
    }
    return return_type::OK;
  }

  return_type prepare_command_mode_switch(const std::vector<std::string> & starts,
                                          const std::vector<std::string> & stops) override
  {
    const auto start = mask(starts);
    const auto stop = mask(stops);
    if (!start || !stop) {
      return return_type::ERROR;
    }
    if (!(*start | *stop)) {
      return return_type::OK;
    }
    prepared_.store(0, std::memory_order_release);
    const unsigned retained = claim_.load(std::memory_order_acquire) & ~(*stop);
    const unsigned next = retained | *start;
    const auto device = capture();
    if (next > 2 || (*start && (!device || !device->healthy || retained != 0))) {
      return return_type::ERROR;
    }
    prepared_generation_.store(device ? device->generation : 0, std::memory_order_relaxed);
    prepared_.store(64 | (next << 4) | (*stop << 2) | *start, std::memory_order_release);
    return return_type::OK;
  }

  return_type perform_command_mode_switch(const std::vector<std::string> & starts,
                                          const std::vector<std::string> & stops) override
  {
    const auto start = mask(starts);
    const auto stop = mask(stops);
    if (!start || !stop) {
      return return_type::ERROR;
    }
    if (!(*start | *stop)) {
      return return_type::OK;
    }
    const unsigned action = prepared_.exchange(0, std::memory_order_acquire);
    if (!(action & 64) || (action & 15) != ((*stop << 2) | *start)) {
      return return_type::ERROR;
    }
    const unsigned next = (action >> 4) & 3;
    if (*start) {
      const auto device = capture();
      if (!device || !device->healthy || device->generation != prepared_generation_.load(std::memory_order_relaxed) ||
          !set_command(commands_[next - 1], std::numeric_limits<double>::quiet_NaN(), false)) {
        return return_type::ERROR;
      }
      claimed_generation_.store(device->generation, std::memory_order_relaxed);
    }
    claim_.store(next, std::memory_order_release);
    return return_type::OK;
  }

private:
  struct Sample
  {
    std::uint64_t sequence;
    std::uint64_t generation;
    std::array<double, 3> values;
    bool healthy;
  };

  /// Read a coherent, finite sample on the device's current boot and clock.
  std::optional<Sample> capture() noexcept
  {
    const auto frame = device_.read();
    if (!frame || (*frame)[1] < observed_generation_.load(std::memory_order_relaxed)) {
      return std::nullopt;
    }
    auto known = observed_generation_.load(std::memory_order_relaxed);
    while (known < (*frame)[1] && !observed_generation_.compare_exchange_weak(known, (*frame)[1], std::memory_order_relaxed)) {}
    if (known > (*frame)[1]) {
      return std::nullopt;
    }
    observed_sequence_.store((*frame)[0], std::memory_order_relaxed);
    const auto now = monotonic_ns();
    Sample result{(*frame)[0], (*frame)[1], {std::bit_cast<double>((*frame)[4]), std::bit_cast<double>((*frame)[5]),
                                          std::bit_cast<double>((*frame)[6])}, false};
    result.healthy = (*frame)[3] == 1 && (*frame)[2] <= now && now - (*frame)[2] <= maximum_age_ &&
                     std::isfinite(result.values[0]) && std::isfinite(result.values[1]) && std::isfinite(result.values[2]);
    return result;
  }

  /// Translate exact resource claim names, ignoring any other joint's interfaces.
  std::optional<unsigned> mask(const std::vector<std::string> & claims) const noexcept
  {
    unsigned result = 0;
    for (const std::string & name : claims) {
      if (!name.starts_with(prefix_)) {
        continue;
      }
      const auto leaf = std::string_view{name}.substr(prefix_.size());
      if (leaf != "position" && leaf != "effort") {
        return std::nullopt;
      }
      result |= leaf == "position" ? 1U : 2U;
    }
    return result;
  }

  /// Publish a safe disabled command when no current generation has authority.
  void inhibit() noexcept
  {
    command_.publish({0, observed_generation_.load(std::memory_order_relaxed), monotonic_ns(), 0, 0,
                      observed_sequence_.load(std::memory_order_relaxed), 0, 0});
  }

  const std::array<const char *, 6> state_keys_ {"position", "velocity", "effort", "drive_generation", "drive_healthy", "drive_authorized_generation"};
  std::array<hardware_interface::StateInterface::SharedPtr, 6> states_;
  std::array<hardware_interface::CommandInterface::SharedPtr, 2> commands_;
  std::string prefix_, device_path_, command_path_;
  Slot device_, command_;
  std::uint64_t maximum_age_ = 0;
  std::atomic<std::uint64_t> observed_generation_{0}, observed_sequence_{0}, claimed_generation_{0}, prepared_generation_{0};
  std::atomic<unsigned> claim_{0}, prepared_{0};
  std::atomic<bool> active_{false};
};
}

PLUGINLIB_EXPORT_CLASS(fenced_drive::FencedSystem, hardware_interface::SystemInterface)
