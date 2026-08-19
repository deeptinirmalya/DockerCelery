#!/bin/bash

# Start Health Check
python health_check.py &

# Main Worker (URL 1) - Listens specifically to the custom priority queue
celery -A worker_dir.connection.worker_app worker \
    -Q priority_celery \
    --loglevel=info --concurrency=1 --hostname=worker1@%h \
    --without-heartbeat --without-gossip --without-mingle &

# Beat Worker (URL 2) - Uses default settings & default queue
celery -A beat_dir.connection.beat_app worker \
    --loglevel=info --concurrency=1 --hostname=worker2@%h \
    --without-heartbeat --without-gossip --without-mingle &

# Beat Scheduler (URL 2)
celery -A beat_dir.connection.beat_app beat \
    --loglevel=info --pidfile=/tmp/celerybeat.pid