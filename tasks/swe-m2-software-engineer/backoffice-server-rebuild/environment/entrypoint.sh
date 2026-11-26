#!/bin/sh
/usr/local/sbin/start-stockwell || true
exec "$@"
