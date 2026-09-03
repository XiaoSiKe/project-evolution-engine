import os, sys, unittest
from pathlib import Path
root = Path(os.environ["EVAL_WORKSPACE"])
sys.path.insert(0, str(root))
from app import exporter, policy
rows=[{"id":1,"owner":"lin","amount":12.5},{"id":2,"owner":"lin","amount":3}]
assert exporter.export_many(rows,"lin")==[exporter.export_one(r,"lin") for r in rows]
assert exporter.export_many([],"lin")==[]
policy.CURRENCY="USD"
assert exporter.export_many(rows,"lin")==["1:USD 12.50","2:USD 3.00"]
with unittest.TestCase().assertRaises(PermissionError): exporter.export_many(rows,"other")
print("Behavior oracle passed.")
