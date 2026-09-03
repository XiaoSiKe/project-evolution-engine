import os
import sys
from pathlib import Path
root = Path(os.environ["EVAL_WORKSPACE"])
sys.path.insert(0, str(root))
from app.api import quote
from app.domain.pricing import amount
assert quote(200)==200
assert quote(200,member=True)==180
assert quote(200,member=False)==200
assert amount(200,member=True)==180
assert amount(200)==200
assert (root/"app/pricing.py").read_text()=="# Legacy utility retained for an old offline importer.\ndef amount(subtotal):\n    return subtotal\n"
print("Behavior oracle passed.")
