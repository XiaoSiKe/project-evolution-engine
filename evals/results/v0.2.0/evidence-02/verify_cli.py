import json
import os
from pathlib import Path
import shlex
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory


project = Path(__file__).resolve().parent.parent / "trial-02"
evidence = Path(__file__).resolve().parent
baseline = json.loads((evidence / "baseline-files.json").read_text())
commands = []


def run_cli(database, command):
    factory = "flaskr:create_app(" + repr(
        {"TESTING": True, "DATABASE": str(database)}
    ) + ")"
    args = [sys.executable, "-m", "flask", "--app", factory, command]
    result = subprocess.run(
        args,
        cwd=project,
        env={**os.environ, "PYTHONPATH": str(project), "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
        capture_output=True,
    )
    record = {
        "command": shlex.join(args),
        "exit_code": result.returncode,
        "outcome": (result.stdout + result.stderr).strip(),
    }
    commands.append(record)
    print(json.dumps(record))
    assert result.returncode == 0, record


with TemporaryDirectory(prefix="cli-", dir=evidence) as temporary:
    temporary = Path(temporary)
    fresh = temporary / "fresh.sqlite"
    run_cli(fresh, "init-db")
    with sqlite3.connect(fresh) as db:
        column = next(row for row in db.execute("PRAGMA table_info(post)") if row[1] == "status")
        assert column[3] == 1 and column[4] == "'published'"

    legacy = temporary / "legacy.sqlite"
    with sqlite3.connect(legacy) as db:
        db.executescript(baseline["flaskr/schema.sql"]["text"])
        db.executescript((project / "tests/data.sql").read_text())
        old_posts = db.execute("SELECT * FROM post ORDER BY id").fetchall()
        old_users = db.execute("SELECT * FROM user ORDER BY id").fetchall()

    run_cli(legacy, "upgrade-db")
    with sqlite3.connect(legacy) as db:
        assert db.execute("SELECT id, author_id, created, title, body FROM post ORDER BY id").fetchall() == old_posts
        assert db.execute("SELECT * FROM user ORDER BY id").fetchall() == old_users
        assert db.execute("SELECT status FROM post").fetchone() == ("published",)
        db.execute("UPDATE post SET status = 'draft' WHERE id = 1")

    run_cli(legacy, "upgrade-db")
    with sqlite3.connect(legacy) as db:
        assert db.execute("SELECT status FROM post WHERE id = 1").fetchone() == ("draft",)
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)

(evidence / "cli-commands.json").write_text(json.dumps(commands, indent=2) + "\n")
print("CLI smoke passed: fresh initialization, legacy upgrade, unchanged credentials/posts, and repeat upgrade preserving a draft.")
