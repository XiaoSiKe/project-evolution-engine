import os
import sys
from pathlib import Path
root = Path(os.environ["EVAL_WORKSPACE"])
sys.path.insert(0, str(root))
from app.contacts import normalize_email,email_domain
from app.checkout import total
assert normalize_email("  A@Example.COM ")=="a@example.com"
assert normalize_email("a@example.com")=="a@example.com"
assert email_domain("a@example.com")=="example.com"
assert total([3,4])==7
assert (root/"app/checkout.py").read_text()=="def total(prices):\n    return sum(prices)\n"
print("Behavior oracle passed.")
