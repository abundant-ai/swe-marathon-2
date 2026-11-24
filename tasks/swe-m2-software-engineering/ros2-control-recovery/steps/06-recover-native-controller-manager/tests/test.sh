#!/bin/bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
exec /usr/bin/python3 -I /tests/verify.py
