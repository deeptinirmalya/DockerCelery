import os
import base64
import binascii
from dotenv import load_dotenv
from .connection import worker_app
import requests
import time
import random

from datetime import datetime, timezone

from github import Github, Auth, GithubException
from github.GithubException import UnknownObjectException
from google import genai
from pushbullet import Pushbullet
from pydantic import ValidationError


from .schema import ReceiptRequest, PaymentReceipt



from datetime import datetime
from google.genai import types
from typing import Dict, Any
import requests
import json
import hmac
import hashlib
import httpx


load_dotenv()


def notify_user(title: str, body: str) -> bool:
    api_key = os.getenv("YOUR_PUSHBULLET_API_KEY")
    if not api_key:
        return False

    try:
        Pushbullet(api_key).push_note(title, body)
        return True
    except Exception as exc:
        print(f"Warning: Pushbullet notification failed: {exc}")
        return False


# ==== for task managet auto recipt adder ===================m = ==================

@worker_app.task(name="extract_transaction_details",
                bind=True, 
                max_retries=3, 
                default_retry_delay=60,
                ignore_result=True  
            )
def extract_transaction_details(
    self,
    payload: ReceiptRequest | Dict[str, Any]
) -> Dict[str, Any]:
    try:
        receipt_request = ReceiptRequest.model_validate(payload)
        b64_data = receipt_request.base64_string.strip()
        if "," in b64_data:
            b64_data = b64_data.split(",")[-1]

        try:
            image_bytes = base64.b64decode(b64_data, validate=True)
        except (binascii.Error, ValueError) as exc:
            failure = {
                "status": "failed",
                "error": "Invalid base64 receipt image.",
                "details": str(exc),
            }
            notify_user(
                "Receipt parsing needs attention",
                "The receipt base64 string is invalid and cannot be recovered by Celery retrying.",
            )
            return failure

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            failure = {
                "status": "failed",
                "error": "GEMINI_API_KEY is missing from the environment.",
            }
            notify_user(
                "Receipt parsing configuration error",
                failure["error"],
            )
            return failure

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version="v1beta"),
        )

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PaymentReceipt,
            temperature=0.1,
        )

        prompt = (
            "Analyze this payment receipt image carefully. Identify the platform used (like PhonePe, GPay, etc.) "
            "and extract the date, time, total amount, sender details, and receiver information. "
            "Return strictly according to the requested JSON schema."
        )

        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=receipt_request.mime_type
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, image_part],
            config=config
        )

        structured_data = PaymentReceipt.model_validate_json(response.text)
        receipt_json = structured_data.model_dump()

        url = os.getenv(
            "RECEIPT_WEBHOOK_URL",
            "https://borax-carnivore-awoke.ngrok-free.dev/api/expenses/background/add-expenses",
        )
        headers = {
            "X-API-Key": os.getenv("MASTER_API_KEY")
        }

        response = requests.post(
            url,
            headers=headers,
            json=receipt_json,
            timeout=30
        )

        response.raise_for_status()
        return {
            "status": "success",
            "receipt": receipt_json,
            "webhook_status_code": response.status_code,
        }

    except Exception as e:
        if isinstance(e, (ValidationError, ValueError)):
            notify_user(
                "Receipt parsing needs attention",
                "The receipt input or Gemini response could not be converted into the required JSON schema.\n"
                f"Error: {e}",
            )
            return {
                "status": "failed",
                "error": str(e),
            }

        if self.request.retries >= self.max_retries:
            notify_user(
                "Receipt parsing failed after retries",
                f"The Celery task exhausted its retries and could not finish.\nError: {e}",
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
        iteration = random.randint(1, 5)

        
        REPO_NAME = "deeptinirmalya/personal"
        BRANCH_NAME = "main"
        file_path = "test.txt" 
        
        repo = g.get_repo(REPO_NAME)

        if random.random() >= 0.70:
            return f"Skipped execution. Count was {iteration}"
        
        for i in range(iteration):
            commit_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            commit_message = f"Update On - {commit_time}"

            file_content = f"updated on {commit_time}"

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
def send_email(
    self,
    authority_name,
    subject,
    body,
    receiver_emails: list[str],
    cc_emails: list[str] | None = None,
    bcc_emails: list[str] | None = None,
    body_type="html",
):
    URL = os.environ.get("EMAIL_API")
    API_KEY = os.environ.get("EMAIL_API_KEY")

    

    payload = {
        "subject": subject,
        "body": body,
        "body_type": body_type,
        "authority_name": authority_name,
        "receiver_email": receiver_emails,
        "cc": cc_emails,
        "bcc": bcc_emails
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
            # print(f"Email to {RECIPIENT}: ❌ API Error {response.status_code}")
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