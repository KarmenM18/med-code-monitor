import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from classifier.classify import classify_diff

TEST_CASES = [
    # CRITICAL - hard rules catches these
    {
        "files": ["lib/determine-basal/determine-basal.js"],
        "patches": {"lib/determine-basal/determine-basal.js": "- var max_iob = 3.0;\n+ var max_iob = 5.0;"},
        "expected": "CRITICAL"
    },
    {
        "files": ["lib/profile/index.js"],
        "patches": {"lib/profile/index.js": "- autosens_max: 1.2\n+ autosens_max: 1.8"},
        "expected": "CRITICAL"
    },
    {
        "files": ["bin/oref0-determine-basal.js"],
        "patches": {"bin/oref0-determine-basal.js": "- var threshold = 60;\n+ var threshold = 80;"},
        "expected": "CRITICAL"
    },
    {
        "files": ["lib/determine-basal/determine-basal.js"],
        "patches": {"lib/determine-basal/determine-basal.js": "- max_daily_safety_multiplier = 3\n+ max_daily_safety_multiplier = 4"},
        "expected": "CRITICAL"
    },
    {
        "files": ["lib/determine-basal/determine-basal.js"],
        "patches": {"lib/determine-basal/determine-basal.js": "- // calculate basal\n+ // calculate basal rate"},
        "expected": "CRITICAL"
    },

    # WARNING - LLM judges these
    {
        "files": ["lib/basal-set-temp.js"],
        "patches": {"lib/basal-set-temp.js": "- var maxRate = profile.max_basal;\n+ var maxRate = profile.max_basal * 1.5;"},
        "expected": "WARNING"
    },
    {
        "files": ["lib/glucose-get-last.js"],
        "patches": {"lib/glucose-get-last.js": "- return glucose[0];\n+ return glucose[1];"},
        "expected": "WARNING"
    },
    {
        "files": ["lib/meal/total.js"],
        "patches": {"lib/meal/total.js": "- carbsAbsorbed = carbs * 0.8;\n+ carbsAbsorbed = carbs * 1.2;"},
        "expected": "WARNING"
    },
    {
        "files": ["lib/calculate-iob/total.js"],
        "patches": {"lib/calculate-iob/total.js": "- iob += bolus.insulin;\n+ iob += bolus.insulin * 0.9;"},
        "expected": "WARNING"
    },
    {
        "files": ["lib/basal-set-temp.js"],
        "patches": {"lib/basal-set-temp.js": "- // set temp basal\n+ // set temporary basal rate"},
        "expected": "SAFE"  
        # comment only change in warning file - LLM should say SAFE
    },

    # SAFE - filter catches these
    {
        "files": ["README.md"],
        "patches": {"README.md": "- old instructions\n+ new instructions"},
        "expected": "SAFE"
    },
    {
        "files": ["CONTRIBUTING.md"],
        "patches": {"CONTRIBUTING.md": "- old text\n+ new text"},
        "expected": "SAFE"
    },
    {
        "files": ["package.json"],
        "patches": {"package.json": '- "version": "0.7.0"\n+ "version": "0.7.1"'},
        "expected": "SAFE"
    },
    {
        "files": ["www/index.html"],
        "patches": {"www/index.html": "- <h1>old</h1>\n+ <h1>new</h1>"},
        "expected": "SAFE"
    },
    {
        "files": [".eslintrc.js"],
        "patches": {".eslintrc.js": "- rule: warn\n+ rule: error"},
        "expected": "SAFE"
    },
]

def run_eval():
    correct = 0
    wrong = []
    false_negatives = []

    print(f"Running eval on {len(TEST_CASES)} test cases...\n")

    for i, case in enumerate(TEST_CASES):
        result = classify_diff(case["files"], case["patches"])
        actual = result["classification"]
        expected = case["expected"]

        if actual == expected:
            correct += 1
            print(f"  ✓ Case {i+1}: {case['files'][0]} → {actual}")
        else:
            wrong.append(case)
            print(f"  ✗ Case {i+1}: {case['files'][0]} → got {actual}, expected {expected}")
            if expected == "CRITICAL" and actual != "CRITICAL":
                false_negatives.append(case)

    precision = correct / len(TEST_CASES) * 100
    print(f"\n--- RESULTS ---")
    print(f"Precision: {precision:.1f}%")
    print(f"Correct: {correct}/{len(TEST_CASES)}")
    print(f"False negatives (critical missed): {len(false_negatives)}")


def run_real_eval():
    with open("eval/real_commits.json", "r") as f:
        cases = json.load(f)

    labeled = [c for c in cases if c["expected"] is not None]

    correct = 0
    false_negatives = []

    print(f"\nRunning eval on {len(labeled)} real oref0 commits...\n")

    for case in labeled:
        result = classify_diff(case["files"], case["patches"])
        actual = result["classification"]
        expected = case["expected"]

        if actual == expected:
            correct += 1
            print(f"  ✓ {case['sha']}: {case['message'][:50]} → {actual}")
        else:
            print(f"  ✗ {case['sha']}: {case['message'][:50]} → got {actual}, expected {expected}")
            if expected == "CRITICAL" and actual != "CRITICAL":
                false_negatives.append(case)

    precision = correct / len(labeled) * 100
    print(f"\n--- REAL COMMITS RESULTS ---")
    print(f"Precision: {precision:.1f}%")
    print(f"Correct: {correct}/{len(labeled)}")
    print(f"False negatives (critical missed): {len(false_negatives)}")

if __name__ == "__main__":
    run_eval()
    print("\n")
    run_real_eval()