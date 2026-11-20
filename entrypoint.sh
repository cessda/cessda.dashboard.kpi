#!/bin/sh
# Run NiceGUI and nginx in one container; exit if either dies so the container restarts.
set -eu

python dashboard.py &
app_pid=$!

nginx -g 'daemon off;' &
nginx_pid=$!

trap 'kill "$app_pid" "$nginx_pid" 2>/dev/null || true' TERM INT

# Wait for the first process to exit, then stop the other
while kill -0 "$app_pid" 2>/dev/null && kill -0 "$nginx_pid" 2>/dev/null; do
    sleep 1
done

kill "$app_pid" "$nginx_pid" 2>/dev/null || true
exit 1
