import os, sys, unittest
from pathlib import Path
root = Path(os.environ["EVAL_WORKSPACE"])
sys.path.insert(0, str(root))
from app.shipping import fee
assert [fee(x) for x in (0,79,80,99,100)]==[10,10,10,10,0]
assert [fee(x,vip=True) for x in (79,80,99,100)]==[10,0,0,0]
assert fee(90,vip=False)==10
print("Behavior oracle passed.")
