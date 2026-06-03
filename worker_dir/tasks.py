import os
from dotenv import load_dotenv
from .connection import worker_app
import requests
import time
import random

from datetime import datetime, timezone

from github import Github, Auth
from github.GithubException import UnknownObjectException


load_dotenv()

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
        raise ValueError("Error: GITHUB_TOKEN not found. Make sure your .env file is set up correctly.")
    
    auth = Auth.Token(token)
    g = Github(auth=auth)

    try:
        user = g.get_user()
        username = user.login

        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        query = f"author:{username} author-date:{today_utc}"
        
        commit_results = g.search_commits(query=query)
        
        commit_count = 0
        for _ in commit_results:
            commit_count += 1
            break
            
        if commit_count == 0:
            iteration = random.randint(2, 5)
            
            REPO_NAME = "any-web-bo/lr"
            BRANCH_NAME = "main"
            file_path = "index.html" 
            
            repo = g.get_repo(REPO_NAME)
            
            for i in range(iteration):
                commit_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                commit_message = f"Automated update - {commit_time}"

                file_content = f"""<!DOCTYPE html>
                                    <html lang="en">
                                    <head>
                                        <meta charset="UTF-8">
                                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                        <title>Updated via Python</title>
                                    </head>
                                    <body>
                                        <h1>Hello World!</h1>
                                        <p>This page was updated directly via the GitHub API using Python.</p>
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
                    time.sleep(2)

        return

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