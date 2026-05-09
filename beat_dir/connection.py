import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

beat_app = Celery(
    'beat_node', 
    broker=os.getenv("BEAT_BROKER_URL"),
    include=['beat_dir.scheduler', 'beat_dir.tasks'] 
)

beat_app.conf.update(
    broker_heartbeat=None,
    task_ignore_result=True,
    worker_send_task_events=False
)

beat_app.conf.beat_schedule = {
    'pulse-every-minute': {
        'task': 'beat_dir.scheduler.heartbeat_check',
        'schedule': 60.0,
    },
}