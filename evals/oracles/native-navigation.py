import os
import sys
from pathlib import Path
root = Path(os.environ["EVAL_WORKSPACE"])
sys.path.insert(0, str(root))
from app.auth import can
assert can("reviewer","view")
assert not can("reviewer","edit") and not can("reviewer","delete")
assert can("admin","delete") and can("editor","edit")
assert not can("editor","delete") and not can("guest","edit")
assert not can("unknown","view")
print("Behavior oracle passed.")
