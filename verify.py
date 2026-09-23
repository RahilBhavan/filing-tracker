"""Reproduce tests, baseline evaluations, and the corrected demo locally."""

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
COMMANDS = [
    ["-m", "unittest", "discover", "-s", "tests", "-v"],
    ["-m", "filing_tracker", "compare", "fixtures/development-pair.json", "--out", "demo/quickstart"],
    ["-m", "filing_tracker", "evaluate", "fixtures/development-pair.json", "--gold", "fixtures/development-gold.json", "--out", "demo/development"],
    ["-m", "filing_tracker", "evaluate", "fixtures/challenge-pair.json", "--gold", "fixtures/challenge-gold.json", "--out", "demo/challenge"],
    ["-m", "filing_tracker", "compare", "fixtures/challenge-pair.json", "--review", "fixtures/challenge-review.json", "--out", "demo/reviewed"],
]


def main():
    runs = []
    for args in COMMANDS:
        process = subprocess.run([sys.executable] + args, cwd=ROOT, capture_output=True, text=True)
        command = "python3 " + " ".join(args)
        record = {"command": command, "exit_status": process.returncode,
                  "stdout": process.stdout,
                  # Elapsed time varies per run; keep the committed record reproducible.
                  "stderr": re.sub(r"(Ran \d+ tests?) in [\d.]+s", r"\1", process.stderr)}
        runs.append(record)
        print("exit=%d %s" % (process.returncode, command))
        if process.returncode:
            print(process.stdout + process.stderr)
            break
    (ROOT / "verification.json").write_text(json.dumps({"python": sys.version.split()[0], "runs": runs}, indent=2) + "\n", encoding="utf-8")
    return runs[-1]["exit_status"]


if __name__ == "__main__":
    sys.exit(main())
