import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
from pushbullet import Pushbullet

load_dotenv()

# Beat uses URL #2
URL_2 = os.getenv("BEAT_BROKER_URL")

beat_app = Celery(
    'beat_node',
    broker=URL_2,
    include=['beat_dir.scheduler_tasks'] 
)





@beat_app.task
def heartbeat_check():
    API_KEY = os.getenv("YOUR_PUSHBULLET_API_KEY")

    pb = Pushbullet(API_KEY)

    push = pb.push_note(
        "Test Title",
        "Hello from Python"
    )

    print("Message Sent")










beat_app.conf.beat_schedule = {
    'pulse-every-minute': {
        'task': 'beat_dir.connection.heartbeat_check',
        'schedule': 60.0,
    },
}