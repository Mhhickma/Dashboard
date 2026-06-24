"""Runtime defaults for dashboard scan jobs.

Python imports this file automatically at startup when the repository root is on
sys.path. The Keepa workflow runs from the repo root, so this lets us tune scan
cadence without hard-coding a larger batch in the workflow file.
"""

import os

# The workflow runs every 15 minutes, which is 96 runs per day.
# Setting the auto-window target to 48 makes the scan cover the ASIN list in
# roughly 12 hours instead of roughly 24 hours.
os.environ["SCAN_RUNS_PER_DAY"] = os.getenv("SCAN_RUNS_PER_DAY", "48")
