from flask import Flask, request, jsonify
import hmac
import hashlib
import json

from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

GITHUB_SECRET = os.getenv('GITHUB_SECRET')

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
        print(f"Push received: {len(commits)} commit(s)")
        for commit in commits:
            print(f"  - {commit['message']}")
            print(f"    Files: {commit.get('modified', [])}")
    
    print("----------------------\n")
    
    return jsonify({'status': 'received'}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'running'}), 200

if __name__ == '__main__':
    app.run(port=3000, debug=True)