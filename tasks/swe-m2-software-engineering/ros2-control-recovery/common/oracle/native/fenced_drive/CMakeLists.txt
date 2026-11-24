cmake_minimum_required(VERSION 3.16)
project(fenced_drive LANGUAGES CXX)

find_package(ament_cmake REQUIRED)
find_package(hardware_interface REQUIRED)
find_package(pluginlib REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)

add_library(fenced_drive SHARED src/system.cpp)
target_compile_features(fenced_drive PRIVATE cxx_std_20)
target_compile_options(fenced_drive PRIVATE -Wall -Wextra -Wpedantic)
ament_target_dependencies(fenced_drive hardware_interface pluginlib rclcpp rclcpp_lifecycle)

pluginlib_export_plugin_description_file(hardware_interface plugins.xml)
install(TARGETS fenced_drive LIBRARY DESTINATION lib)
install(PROGRAMS scripts/recover_drive DESTINATION lib/${PROJECT_NAME})
ament_package()
