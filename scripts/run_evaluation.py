#!/usr/bin/env python3
"""Run evaluation suite runner shortcut."""
import sys
import subprocess
from pathlib import Path

if __name__ == "__main__":
    eval_script = Path(__file__).resolve().parent.parent / "evaluation" / "run_evaluation.py"
    cmd = [sys.executable, str(eval_script)] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
