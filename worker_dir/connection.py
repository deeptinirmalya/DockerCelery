import os
from celery import Celery
from dotenv import load_dotenv
from kombu import Queue

load_dotenv()

# Worker uses URL #1
URL_1 = os.getenv("WORKER_BROKER_URL")

worker_app = Celery(
    'worker_node',
    broker=URL_1,
    include=['worker_dir.tasks']
)

worker_app.conf.update(
    # --- QUEUE & PRIORITY SETTINGS ---
    task_default_queue='priority_celery',             # Sets default queue to priority_celery
    task_queue_max_priority=10,            
    task_default_priority=5,                
    task_queues=[
        Queue(
            'priority_celery',                       
            queue_arguments={'x-max-priority': 10}  
        ),
    ],
    task_routes={
        'worker_dir.tasks.*': {'queue': 'priority_celery'}, # Automatically routes all tasks in worker_dir.tasks
    },

    # --- PERFORMANCE & COST SAVING ---
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    
    # --- REQUEST SAVING (Crucial for 1M limit) ---
    worker_send_task_events=False,      
    task_ignore_result=True,           
    worker_enable_remote_control=False, 
    
    # --- CONNECTION SETTINGS ---
    broker_pool_limit=1,               
    broker_connection_timeout=30,      
    broker_heartbeat=None              
)