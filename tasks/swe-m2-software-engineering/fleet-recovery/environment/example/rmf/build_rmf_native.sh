#!/bin/sh
set -eu
source=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root=${RMF_ROOT:-/opt/fleet-rmf}
ros="$root/opt/ros/jazzy"
lib="$root/usr/lib/x86_64-linux-gnu"
exec g++ -std=c++17 -O2 -Wall -Wextra -I"$ros/include" -I"${EIGEN_INCLUDE:-/usr/include/eigen3}" \
 "$source/rmf_native.cpp" -L"$ros/lib/x86_64-linux-gnu" -L"$ros/lib" \
 "-Wl,--disable-new-dtags,-rpath,$ros/lib/x86_64-linux-gnu:$ros/lib:$lib" \
 "-Wl,-rpath-link,$lib" -lrmf_traffic -lrmf_utils -o "${1:-./rmf-native}"
