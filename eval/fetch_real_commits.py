import sys
import os
import json
import requests
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from dotenv import load_dotenv
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = "openaps/oref0"  # pull from the real repo not your fork

def fetch_commit_diff(sha):
    url = f"https://api.github.com/repos/{REPO}/commits/{sha}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    data = response.json()

    files_changed = []
    patches = {}
    for file in data.get("files", []):
        filename = file["filename"]
        files_changed.append(filename)
        patches[filename] = file.get("patch", "")

    return files_changed, patches

def fetch_recent_commits(n=50):
    url = f"https://api.github.com/repos/{REPO}/commits"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers, params={"per_page": n})
    return response.json()

def auto_label(files_changed):
    CRITICAL_FILES = [
        "lib/determine-basal/determine-basal.js",
        "lib/profile/index.js",
        "bin/oref0-determine-basal.js"
    ]

    WARNING_PATHS = [
        "lib/basal-set-temp.js",
        "lib/glucose-get-last.js",
        "lib/meal/total.js",
        "lib/iob/",
        "lib/calculate-iob/",
        "lib/determine-basal/"  # subfolders not the main file
    ]

    SAFE_PATHS = [
        "README.md", "package.json", ".gitignore",
        "CONTRIBUTING.md", "LICENSE.txt", "www/",
        "examples/", "bin/oref0-setup.sh",
        "bin/oref0-pump-loop.sh", "bin/oref0-ns-loop.sh",
        "bin/", "tests/"
    ]

    for file in files_changed:
        if file in CRITICAL_FILES:
            return "CRITICAL"

    for file in files_changed:
        for path in WARNING_PATHS:
            if file == path or file.startswith(path):
                return "WARNING"

    return "SAFE"

if __name__ == "__main__":
    print("Fetching real commits from openaps/oref0...\n")
    commits = fetch_recent_commits(50)

    real_cases = []
    for commit in commits:
        sha = commit["sha"]
        message = commit["commit"]["message"].split("\n")[0]
        files_changed, patches = fetch_commit_diff(sha)

        if not files_changed:
            continue

        label = auto_label(files_changed)  # auto label here

        real_cases.append({
            "sha": sha[:7],
            "message": message,
            "files": files_changed,
            "patches": patches,
            "expected": label  # already filled in
        })

    with open("eval/real_commits.json", "w") as f:
        json.dump(real_cases, f, indent=2)

    print(f"Saved {len(real_cases)} commits to eval/real_commits.json")
    print("Now open the file and add 'expected' labels manually")


