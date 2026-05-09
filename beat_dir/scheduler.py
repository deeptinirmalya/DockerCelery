import os
from .connection import beat_app
from pushbullet import Pushbullet

@beat_app.task(name="beat_dir.scheduler.heartbeat_check")
def heartbeat_check():
    try:
        pb = Pushbullet(os.getenv("YOUR_PUSHBULLET_API_KEY"))
        pb.push_note("Pulse", "System is healthy!")
        # print("Success: Message sent to Pushbullet")
    except Exception as e:
        print(f"Error: {e}")