#!/bin/bash
set -e

# Copy default config if not exists
if [ ! -f /data/config.json ]; then
    echo "No config.json found in /data, copying default..."
    cp /app/config.example.json /data/config.json
fi

exec "$@"
