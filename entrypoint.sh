#!/bin/bash

# Start Health Check
python health_check.py &

# Main Worker (URL 1)
celery -A worker_dir.connection.worker_app worker \
    --loglevel=info --concurrency=1 --hostname=worker1@%h \
    --without-heartbeat --without-gossip --without-mingle &

# Beat Worker (URL 2)
celery -A beat_dir.connection.beat_app worker \
    --loglevel=info --concurrency=1 --hostname=worker2@%h \
    --without-heartbeat --without-gossip --without-mingle &

# Beat Scheduler (URL 2)
celery -A beat_dir.connection.beat_app beat \
    --loglevel=info --pidfile=/tmp/celerybeat.pid