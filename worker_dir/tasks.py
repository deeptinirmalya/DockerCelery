import os
from dotenv import load_dotenv
from .connection import worker_app
import requests
import time
import random

from datetime import datetime, timezone

from github import Github, Auth, GithubException
from github.GithubException import UnknownObjectException

from .services import extract_navi_transaction, extract_phonepe_transaction, _sanitize_phonepe_data, extract_gpay_transaction, _sanitize_gpay_data





from datetime import datetime
from typing import Dict, Any
import requests
import json
import hmac
import hashlib
import httpx


load_dotenv()
# ==== for task managet auto recipt adder ===================m = ==================

@worker_app.task(name="extract_transaction_from_telegram",
                bind=True, 
                max_retries=3, 
                default_retry_delay=60,
                ignore_result=True  
            )
def extract_transaction_from_telegram(
    self,
    chat_id: int,
    caption: str,
    file_id: str,
    bot_token: str,
    gemini_api_key: str,
    platform: str,
    model: str = "gemini-2.5-flash",
) -> Dict[str, Any]:
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": f"Details reached at celery ✅\n processing...."
                }
            )
        platform = platform.lower().strip()
        
        if platform in ["navi"]:
            payload = {
                "sucess": True,
                "error": None,
                "data": {
                    "result": extract_navi_transaction(file_id, bot_token, gemini_api_key, model),
                    "chat_id": chat_id,
                    "caption": caption
                }
            }
        elif platform in ["phonepe", "phonpe", "phone_pe"]:
            payload = {
                "sucess": True,
                "error": None,
                "data": {
                    "result": extract_phonepe_transaction(file_id, bot_token, gemini_api_key, model),
                    "chat_id": chat_id,
                    "caption": caption
                }
            }
        elif platform in ["gpay", "google_pay", "google pay", "googlepay"]:
            payload = {
                "sucess": True,
                "error": None,
                "data": {
                    "result": extract_gpay_transaction(file_id, bot_token, gemini_api_key, model),
                    "chat_id": chat_id,
                    "caption": caption
                }
            }
        else:
            payload = {
                "sucess": False,
                "error": f"Unknown platform: {platform}. Use 'navi', 'phonepe', or 'gpay'",
                "data": None
            }

        url = "https://borax-carnivore-awoke.ngrok-free.dev/api/expenses/telegram/add-expenses"
        headers = {
            "X-API-Key": os.getenv("MASTER_API_KEY")
        }

        json_payload = payload
        response = requests.post(
            url,
            headers=headers,
            json=json_payload,
            timeout=30
        )

        response.raise_for_status()

        # requests.post(
        #     f"https://api.telegram.org/bot{bot_token}/sendMessage",
        #     json={
        #         "chat_id": chat_id,
        #         "text": f"Details sent from celery ✅"
        #         }
        #     )

    except Exception as e:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": f"Process fail at celery ❌ \n retrying..."
                }
            )
        raise self.retry(exc=e)

# =====  for github ============================
@worker_app.task(
    name="commiter",
    bind=True,
    max_retries=3, 
    default_retry_delay=60,
    ignore_result=True
)
def commiter(self):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("Error: GITHUB_TOKEN not found.")
    
    auth = Auth.Token(token)
    g = Github(auth=auth)

    try:
        user = g.get_user()
        username = user.login
        iteration = random.randint(2, 10)
        
        REPO_NAME = "deeptinirmalya/SVD-TECH"
        BRANCH_NAME = "main"
        file_path = "test.txt" 
        
        repo = g.get_repo(REPO_NAME)
        
        for i in range(iteration):
            commit_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            commit_message = f"Update On - {commit_time}"

            file_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Updated</title>
</head>
<body>
    <h1>Hello World!</h1>
    <p>This page was updated directly</p>
    <p>Last updated: {commit_time} (Iteration {i+1})</p>
</body>
</html>"""

            contents = repo.get_contents(file_path, ref=BRANCH_NAME)
            
            repo.update_file(
                path=file_path,
                message=commit_message,
                content=file_content,
                sha=contents.sha, 
                branch=BRANCH_NAME
            )
            
            if i < iteration - 1:
                time.sleep(random.uniform(4.0, 7.0))
                
        return f"count is {iteration}"
    except GithubException as e:
        if e.status == 403 or e.status == 429:
            raise self.retry(exc=e, countdown=300)
        raise self.retry(exc=e)

    except Exception as exc:
        raise self.retry(exc=exc)


# ======================================***************************============================================================================================

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
        result = f"Status {response.status_code}: {response.text}"

        
        if response.status_code == 200:
            return f"✅ SUCCESS == {result}"
        else:
            print(f"Email to {RECIPIENT}: ❌ API Error {response.status_code}")
            raise self.retry(countdown=60)

    except Exception as e:
        raise self.retry(exc=e)

#======      for WEBHOOK for secret manager ======================================

@worker_app.task(
                name="send_webhook_task",
                bind=True, 
                max_retries=3, 
                default_retry_delay=60,
                ignore_result=True  
)
def send_webhook_task(self, client_endpoint_url: str, webhook_secret: str, payload: dict):
    try:

        raw_body = json.dumps(payload, separators=(',', ':')).encode("utf-8")

        print("RAW BODY:", raw_body)
        print("SECRET:", repr(webhook_secret))


        signature = hmac.new(
            webhook_secret.encode('utf-8') if isinstance(webhook_secret, str) else webhook_secret,
            msg=raw_body,
            digestmod=hashlib.sha256
        ).hexdigest()


        headers = {
            "Content-Type": "application/json",
            "X-Signature": signature
        }


        with httpx.Client(timeout=10.0) as client:
            response = client.post(client_endpoint_url, content=raw_body, headers=headers)

            response.raise_for_status()

        return {
            "status_code": response.status_code,
            "url": client_endpoint_url,
            "response": response.text
        }

    except Exception as exc:
        raise self.retry(exc=exc)