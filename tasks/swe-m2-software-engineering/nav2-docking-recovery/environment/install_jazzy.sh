#!/bin/sh
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl python3 python3-venv
curl --fail --location --silent --show-error \
    https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros2-archive-keyring.gpg
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/ros2-archive-keyring.gpg] https://repo.ros2.org/ubuntu/main noble main' \
    > /etc/apt/sources.list.d/ros2.list
apt-get update
apt-get install -y --no-install-recommends \
    ros-jazzy-opennav-docking=1.3.14-1noble.20261109.091645 \
    ros-jazzy-rclpy ros-jazzy-rmw-cyclonedds-cpp ros-jazzy-std-msgs
apt-get clean
rm -rf /var/lib/apt/lists/*
