#!/bin/bash

python health_check.py &


celery -A worker_dir.connection.worker_app worker \
    --loglevel=info \
    --concurrency=1 \
    --without-heartbeat \
    --without-gossip \
    --without-mingle &


celery -A beat_dir.connection.beat_app beat \
    --loglevel=info \
    --pidfile=/tmp/celerybeat.pid