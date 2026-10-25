"""Reproduce tests, baseline evaluations, and the corrected demo locally."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
# Placeholder "{demo}" is the demo output root: build/ by default, the tracked demo/ with --update.
COMMANDS = [
    ["-m", "unittest", "discover", "-s", "tests", "-v"],
    ["-m", "filing_tracker", "compare", "fixtures/development-pair.json", "--out", "{demo}/quickstart"],
    ["-m", "filing_tracker", "evaluate", "fixtures/development-pair.json", "--gold", "fixtures/development-gold.json", "--out", "{demo}/development"],
    ["-m", "filing_tracker", "evaluate", "fixtures/challenge-pair.json", "--gold", "fixtures/challenge-gold.json", "--out", "{demo}/challenge"],
    ["-m", "filing_tracker", "compare", "fixtures/challenge-pair.json", "--review", "fixtures/challenge-review.json", "--out", "{demo}/reviewed"],
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true",
                        help="rewrite the tracked demo/ and verification.json (default writes to build/)")
    update = parser.parse_args(argv).update
    demo = "demo" if update else "build/demo"
    record_path = ROOT / ("verification.json" if update else "build/verification.json")
    record_path.parent.mkdir(parents=True, exist_ok=True)
    runs = []
    for template in COMMANDS:
        args = [a.replace("{demo}", demo) for a in template]
        process = subprocess.run([sys.executable] + args, cwd=ROOT, capture_output=True, text=True)
        # Record the canonical demo/ path so the committed record is the same either way.
        command = "python3 " + " ".join(a.replace(demo, "demo") for a in args)
        record = {"command": command, "exit_status": process.returncode,
                  "stdout": process.stdout,
                  # Elapsed time varies per run; keep the committed record reproducible.
                  "stderr": re.sub(r"(Ran \d+ tests?) in [\d.]+s", r"\1", process.stderr)}
        runs.append(record)
        print("exit=%d %s" % (process.returncode, command))
        if process.returncode:
            print(process.stdout + process.stderr)
            break
    record_path.write_text(json.dumps({"python": sys.version.split()[0], "runs": runs}, indent=2) + "\n", encoding="utf-8")
    return runs[-1]["exit_status"]


if __name__ == "__main__":
    sys.exit(main())
