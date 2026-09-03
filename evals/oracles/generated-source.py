import os
import sys
from pathlib import Path
root = Path(os.environ["EVAL_WORKSPACE"])
sys.path.insert(0, str(root))
import json,subprocess
from app.statuses import VALID_STATUSES
assert VALID_STATUSES==("queued","running","done","cancelled")
assert json.loads((root/"schema/statuses.json").read_text())==list(VALID_STATUSES)
paths=[root/"app/statuses.py",root/"docs/statuses.md"]
before=[p.read_bytes() for p in paths]
subprocess.run([sys.executable,"scripts/generate.py"],cwd=root,check=True)
assert [p.read_bytes() for p in paths]==before,"Generated outputs were not current/idempotent"
print("Behavior oracle passed.")
