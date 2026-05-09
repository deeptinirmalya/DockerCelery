import os
from dotenv import load_dotenv
from .connection import worker_app
import requests

load_dotenv()


@worker_app.task(name="send_email",
                bind=True, 
                max_retries=3, 
                default_retry_delay=60,
                ignore_result=True  
            )
def send_email(self, subject, body, email):
    URL = os.environ.get("EMAIL_API")
    API_KEY = os.environ.get("EMAIL_API_KEY")
    RECIPIENT = str(email)
    

    payload = {
        "subject": subject,
        "body": body,
        "receiver_email": RECIPIENT,
        "authority_name": f"STARTUP",
        "body_type": "html"
    }

    headers = {
        "X-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(URL, json=payload, headers=headers)
        result = f"Status {response.status_code}: {response.text}: email ={email}"

        
        if response.status_code == 200:
            return f"✅ SUCCESS == {result}"
        else:
            print(f"Email to {RECIPIENT}: ❌ API Error {response.status_code}")
            raise self.retry(countdown=60)

        
    except Exception as e:
        raise self.retry(exc=e)