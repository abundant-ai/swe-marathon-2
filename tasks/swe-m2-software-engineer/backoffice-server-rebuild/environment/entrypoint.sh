#!/bin/sh
/usr/local/sbin/start-sealed-server || true
exec "$@"
