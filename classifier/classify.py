"""
Input:
- list of changed files
- differene between current and previous commit

Processing:
- LLM processing to process changes against FDA compliance standards

Output:
- classification 
- severity
- explanation
- files flagged
- regulation reference
- requires_review T/F parameter


2 types of warnings:
- critical errors
- warnings
- safe

"""


from groq import Groq
import os
import json
import time

from dotenv import load_dotenv
load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# model = genai.GenerativeModel(
#     model_name="gemini-1.5-flash",  # free tier model
#     system_instruction="prompt"
# )

# response = model.generate_content("the diff content")
# result = response.text

# def changed_files():
#     if "lib/determime-basal/" in changed_files:
#         severity = "CRITICAL"

SYSTEM_PROMPT = """
You are a medical device compliance officer reviewing code changes 
to OpenAPS oref0 — open source insulin dosing software used by 
2,700+ Type 1 diabetic patients to automatically control insulin 
delivery via their pumps. A bug in this code can cause insulin 
overdose or underdose, both of which are life-threatening.

Classify each code change using these exact rules:

CRITICAL — any change to these files, no exceptions:
- lib/determine-basal/determine-basal.js (core dosing algorithm)
- lib/profile/index.js (safety parameter loading)
- bin/oref0-determine-basal.js (algorithm entry point)

Also CRITICAL if any change modifies these specific variables 
anywhere in the codebase:
- max_iob
- max_daily_safety_multiplier  
- current_basal_safety_multiplier
- autosens_max or autosens_min
- any numeric value compared against blood glucose

WARNING — changes to these files where the LLM must judge 
based on what actually changed in the diff:
- lib/basal-set-temp.js
- lib/calculate-iob/ (any file in this folder)
- lib/glucose-get-last.js
- lib/meal/total.js
- tests/ (especially if test coverage is being removed)

SAFE — always safe, never flag:
- README.md, CONTRIBUTING.md, LICENSE.txt
- www/, examples/, .github/
- logrotate.*, .eslintrc.js, package.json

You must respond in JSON only. 
No preamble. No explanation outside the JSON. 
No markdown backticks. Exactly this structure:

{
  "classification": "CRITICAL" or "WARNING" or "SAFE",
  "severity": "HIGH" or "MEDIUM" or "LOW",
  "explanation": "one paragraph in plain English for a non-technical compliance officer",
  "files_flagged": ["list of filenames that triggered the flag"],
  "requires_review": true or false,
  "reviewer_type": "compliance_officer" or "senior_engineer" or "none"
}
"""

with open("policies/critical.json", "r") as f:
    critical_rules = json.load(f)

with open("policies/warning.json", "r") as f:
    warning_rules = json.load(f)

with open("policies/safe.json", "r") as f:
    safe_rules = json.load(f)

CRITICAL_FILES = critical_rules["critical_files"]
CRITICAL_VARIABLES = critical_rules["critical_variables"]
WARNING_PATHS = warning_rules["warning_paths"]
SAFE_PATHS = safe_rules["safe_paths"]


# Load model once
# MODEL = genai.GenerativeModel(
#     model_name="gemini-1.5-flash",
#     system_instruction=SYSTEM_PROMPT
# )

# Rules engine for critical changes
def check_hard_rules(files_changed, patches):

    flagged_files = []

    # critical file detection
    for file in files_changed:
        if file in CRITICAL_FILES:
            flagged_files.append(file)

    # critical variable detection
    for filename, diff in patches.items():
        for variable in CRITICAL_VARIABLES:
            if variable in diff:
                flagged_files.append(filename)

    if flagged_files:
        return {
            "classification": "CRITICAL",
            "severity": "HIGH",
            "explanation": "Changes affect insulin dosing logic or safety constraints requiring mandatory review.",
            "files_flagged": list(set(flagged_files)),
            "requires_review": True,
            "reviewer_type": "senior_engineer"
        }

    return None

def classify_diff(files_changed, patches):
    """
    files_changed: list of filenames ["lib/determine-basal/determine-basal.js"]
    patches: dict of filename -> diff string {"lib/determine-basal/determine-basal.js": "@@ ..."}
    returns: dict with classification result
    """

    hard_result = check_hard_rules(files_changed, patches)

    if hard_result:
        return hard_result

    # Remove safe files
    filtered_files = []

    for file in files_changed:
        is_safe = False

        for safe_path in SAFE_PATHS:
            if file == safe_path or file.startswith(safe_path):
                is_safe = True
                break

        if not is_safe:
            filtered_files.append(file)
    
    # Keep only warning-monitored files
    warning_files = []

    for file in filtered_files:
        for warning_path in WARNING_PATHS:
            if file == warning_path or file.startswith(warning_path):
                warning_files.append(file)
                break

    # Return SAFE immediately if no critical/warning files were touched
    if not warning_files:
        return {
            "classification": "SAFE",
            "severity": "LOW",
            "explanation": "Only documentation or non-functional files were changed.",
            "files_flagged": [],
            "requires_review": False,
            "reviewer_type": "none"
        }

    # build the message with all changed files and their diffs
    user_message = "Review the following code changes and classify them:\n\n"
    for filename in filtered_files:
        patch = patches.get(filename, "No diff available")
        user_message += f"File: {filename}\n"
        user_message += f"Diff:\n{patch}\n"
        user_message += "---\n"

    # response = MODEL.generate_content(user_message)
    # raw = response.text.strip()

    response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
        ]
    )
    raw = response.choices[0].message.content.strip()

    # clean up if gemini adds backticks
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(cleaned)

    return result


# standalone test
if __name__ == "__main__":
    print("--- TEST 1: Should be CRITICAL ---")
    result = classify_diff(
        files_changed=["lib/determine-basal/determine-basal.js"],
        patches={
            "lib/determine-basal/determine-basal.js": """
@@ -142,7 +142,7 @@
-  var max_iob = 3.0;
+  var max_iob = 5.0;
            """
        }
    )
    print(json.dumps(result, indent=2))

    print("\n--- TEST 2: Should be SAFE ---")
    result = classify_diff(
        files_changed=["README.md"],
        patches={
            "README.md": """
@@ -1,3 +1,3 @@
- Old installation instructions
+ Updated installation instructions
            """
        }
    )
    print(json.dumps(result, indent=2))

    time.sleep(10)

    print("\n--- TEST 3: Should be WARNING ---")
    result = classify_diff(
        files_changed=["lib/basal-set-temp.js"],
        patches={
            "lib/basal-set-temp.js": """
    @@ -10,7 +10,7 @@
    -  var maxRate = profile.max_basal;
    +  var maxRate = profile.max_basal * 1.5;
            """
        }
    )
    print(json.dumps(result, indent=2))



