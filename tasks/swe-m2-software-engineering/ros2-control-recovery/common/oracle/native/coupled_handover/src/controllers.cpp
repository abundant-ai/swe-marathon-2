#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <string>
#include <vector>

#include "controller_interface/chainable_controller_interface.hpp"
#include "controller_interface/controller_interface.hpp"
#include "pluginlib/class_list_macros.hpp"

namespace coupled_handover
{
constexpr double no_value = std::numeric_limits<double>::quiet_NaN();
constexpr std::size_t observations = 13;
const std::array<std::string, observations> channels = {
  "left/position", "left/velocity", "right/position", "right/velocity",
  "feedback/strain", "feedback/goal", "feedback/goal_velocity",
  "feedback/epoch", "feedback/healthy", "feedback/required_epoch",
  "feedback/weight_left", "feedback/weight_right", "feedback/sample"};

using ControllerStatus = controller_interface::return_type;
using Callback = controller_interface::CallbackReturn;
using Config = controller_interface::InterfaceConfiguration;
const auto exact = controller_interface::interface_configuration_type::INDIVIDUAL;

class ForcePair final : public controller_interface::ChainableControllerInterface
{
public:
  Callback on_init() override { return Callback::SUCCESS; }

  Config command_interface_configuration() const override
  {
    return {exact, {"left/effort", "right/effort"}};
  }

  Config state_interface_configuration() const override
  {
    return {exact, {"feedback/weight_left", "feedback/weight_right"}};
  }

  std::vector<hardware_interface::CommandInterface::SharedPtr>
  on_export_reference_interfaces_list() override
  {
    const auto name = get_node()->get_name();
    return {
      std::make_shared<hardware_interface::CommandInterface>(name, "left_effort", &input_[0]),
      std::make_shared<hardware_interface::CommandInterface>(name, "right_effort", &input_[1]),
    };
  }

  ControllerStatus update_reference_from_subscribers(
    const rclcpp::Time&, const rclcpp::Duration&) override
  {
    input_.fill(no_value);
    return ControllerStatus::OK;
  }

  ControllerStatus update_and_write_commands(
    const rclcpp::Time&, const rclcpp::Duration& period) override
  {
    const double slew = 100 * std::clamp(period.seconds(), 0.0, .02);
    for (std::size_t i = 0; i < output_.size(); ++i)
    {
      const double weight = state_interfaces_[i].get_optional().value_or(0);
      if (!std::isfinite(output_[i]))
        output_[i] = weight;
      const double requested = std::isfinite(input_[i]) ? std::clamp(input_[i], 0.0, 105.0) : output_[i];
      output_[i] += std::clamp(requested - output_[i], -slew, slew);
      if (!command_interfaces_[i].set_value(output_[i]))
        return ControllerStatus::ERROR;
    }
    return ControllerStatus::OK;
  }

private:
  std::array<double, 2> input_{no_value, no_value};
  std::array<double, 2> output_{no_value, no_value};
};

class LiftSupervisor final : public controller_interface::ControllerInterface
{
public:
  Callback on_init() override
  {
    auto_declare<std::string>("policy", "tracking");
    auto_declare<double>("coupling_stiffness_n_per_m", 110.0);
    auto_declare<double>("coupling_damping_ns_per_m", 5.0);
    return Callback::SUCCESS;
  }

  Callback on_configure(const rclcpp_lifecycle::State&) override
  {
    policy_ = get_node()->get_parameter("policy").as_string();
    stiffness_ = get_node()->get_parameter("coupling_stiffness_n_per_m").as_double();
    damping_ = get_node()->get_parameter("coupling_damping_ns_per_m").as_double();
    if ((policy_ != "tracking" && policy_ != "bridge") || stiffness_ <= 0 || damping_ <= 0)
      return Callback::ERROR;
    return Callback::SUCCESS;
  }

  Callback on_activate(const rclcpp_lifecycle::State&) override
  {
    estimated_skew_ = no_value;
    return Callback::SUCCESS;
  }

  Config command_interface_configuration() const override
  {
    return {exact, {"pair/left_effort", "pair/right_effort"}};
  }

  Config state_interface_configuration() const override
  {
    return {exact, {channels.begin(), channels.end()}};
  }

  ControllerStatus update(const rclcpp::Time&, const rclcpp::Duration& period) override
  {
    std::array<double, observations> sample;
    for (std::size_t i = 0; i < sample.size(); ++i)
      sample[i] = state_interfaces_[i].get_optional().value_or(no_value);
    const auto [ql, vl, measured_qr, measured_vr, strain, goal, velocity,
      epoch, healthy, required, left_weight, right_weight, sequence] = sample;
    if (!(std::isfinite(ql) && std::isfinite(strain) && sequence > 0))
      return ControllerStatus::OK;

    const bool current = healthy == 1.0 && epoch == required;
    if (policy_ == "tracking" && !current)
      return ControllerStatus::OK;

    double qr = measured_qr, vr = measured_vr;
    if (policy_ != "tracking")
    {
      if (!std::isfinite(estimated_skew_))
        estimated_skew_ = strain / stiffness_;
      const double dt = std::clamp(period.seconds(), .001, .025);
      estimated_skew_ += -std::expm1(-stiffness_ * dt / damping_)
        * (strain / stiffness_ - estimated_skew_);
      qr = ql - estimated_skew_;
      vr = vl - (strain - stiffness_ * estimated_skew_) / damping_;
    }

    constexpr double kp = 205, kd = 53;
    const std::array<double, 2> output = {
      left_weight + kp * (goal - ql) + kd * (velocity - vl) + .70 * strain,
      right_weight + kp * (goal - qr) + kd * (velocity - vr) - .70 * strain,
    };
    for (std::size_t i = 0; i < output.size(); ++i)
      if (!command_interfaces_[i].set_value(output[i]))
        return ControllerStatus::ERROR;
    return ControllerStatus::OK;
  }

private:
  std::string policy_;
  double estimated_skew_ = no_value;
  double stiffness_ = 110.0;
  double damping_ = 5.0;
};
}

PLUGINLIB_EXPORT_CLASS(coupled_handover::ForcePair, controller_interface::ChainableControllerInterface)
PLUGINLIB_EXPORT_CLASS(coupled_handover::LiftSupervisor, controller_interface::ControllerInterface)
