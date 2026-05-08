from flask import Flask, request, jsonify
import hmac
import hashlib
import json

from dotenv import load_dotenv
import os

import requests
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from classifier.classify import classify_diff
load_dotenv()

app = Flask(__name__)

GITHUB_SECRET = os.getenv('GITHUB_SECRET')


def get_commit_files(repo_full_name, commit_sha):
    url = f"https://api.github.com/repos/{repo_full_name}/commits/{commit_sha}"
    headers = {"Authorization": f"token {os.getenv('GITHUB_TOKEN')}"}
    response = requests.get(url, headers=headers)
    data = response.json()

    files_changed = []
    patches = {}
    for file in data.get("files", []):
        filename = file["filename"]
        files_changed.append(filename)
        patches[filename] = file.get("patch", "")

    return files_changed, patches

@app.route('/webhook', methods=['POST'])
def webhook():
    # verify request is actually from github
    signature = request.headers.get('X-Hub-Signature-256', '')
    body = request.get_data()
    
    expected = 'sha256=' + hmac.new(
        GITHUB_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected):
        return jsonify({'error': 'invalid signature'}), 401
    
    # parse the payload github sent
    payload = request.json
    event_type = request.headers.get('X-GitHub-Event')
    
    print(f"\n--- EVENT RECEIVED ---")
    print(f"Event type: {event_type}")
    
    if event_type == 'pull_request':
        pr_number = payload['pull_request']['number']
        pr_title = payload['pull_request']['title']
        action = payload['action']
        print(f"PR #{pr_number}: {pr_title} ({action})")
    
    elif event_type == 'push':
        commits = payload.get('commits', [])
        repo_full_name = payload['repository']['full_name']
        print(f"Push received: {len(commits)} commit(s)")

        for commit in commits:
            sha = commit['id']
            message = commit['message']
            print(f"  - {message} ({sha[:7]})")

            files_changed, patches = get_commit_files(repo_full_name, sha)
            print(f"    Files: {files_changed}")

            result = classify_diff(files_changed, patches)

            print(f"    Classification: {result['classification']}")
            print(f"    Severity: {result['severity']}")
            print(f"    Explanation: {result['explanation']}")
            print(f"    Requires review: {result['requires_review']}")
    
    print("----------------------\n")
    
    return jsonify({'status': 'received'}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'running'}), 200

if __name__ == '__main__':
    app.run(port=3000, debug=True)