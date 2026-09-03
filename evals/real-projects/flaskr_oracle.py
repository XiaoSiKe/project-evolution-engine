from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

workspace = Path(sys.argv[1]).resolve()
mode = sys.argv[2] if len(sys.argv) > 2 else "all"
sys.path.insert(0, str(workspace))
from flaskr import create_app
from flaskr.db import get_db, init_db
from werkzeug.security import generate_password_hash

ORIGINAL_SCHEMA = (Path(__file__).parent / "fixtures/flaskr/flaskr/schema.sql").read_text()
definitions = []
checks = []


def case(name, kind):
    def register(fn):
        definitions.append((name, kind, fn))
        return fn
    return register


def application(old=False):
    temp = tempfile.TemporaryDirectory()
    database = Path(temp.name) / "app.sqlite"
    app = create_app({"TESTING": True, "DATABASE": str(database), "SECRET_KEY": "isolated-test-secret"})
    with app.app_context():
        db = get_db()
        if old:
            db.executescript(ORIGINAL_SCHEMA)
        else:
            init_db()
        for name in ("writer", "other"):
            db.execute("INSERT INTO user (username, password) VALUES (?, ?)",
                       (name, generate_password_hash("pw", method="pbkdf2:sha256:1000")))
        db.commit()
    return temp, app


def login(client, name="writer"):
    assert client.post("/auth/login", data={"username": name, "password": "pw"}).status_code == 302


def post_row(app, title):
    with app.app_context():
        row = get_db().execute("SELECT * FROM post WHERE title=?", (title,)).fetchone()
        return dict(row) if row else None


def add_post(app, title, author=1, status=None):
    with app.app_context():
        db = get_db()
        if status is None:
            cursor = db.execute("INSERT INTO post (title, body, author_id) VALUES (?, ?, ?)", (title, "body", author))
        else:
            cursor = db.execute("INSERT INTO post (title, body, author_id, status) VALUES (?, ?, ?, ?)",
                                (title, "body", author, status))
        db.commit()
        return cursor.lastrowid


@case("existing_crud_and_author_protection", "preserved")
def existing_crud():
    temp, app = application()
    try:
        client = app.test_client()
        assert client.get("/create").status_code == 302
        login(client)
        assert client.post("/create", data={"title": "ordinary", "body": "body"}).status_code == 302
        row = post_row(app, "ordinary")
        client.post(f"/{row['id']}/update", data={"title": "updated", "body": "new"})
        assert post_row(app, "updated")
        other = app.test_client()
        login(other, "other")
        assert other.post(f"/{row['id']}/delete").status_code == 403
        assert client.post(f"/{row['id']}/delete").status_code == 302
        assert not post_row(app, "updated")
    finally:
        temp.cleanup()


@case("existing_invalid_title_is_rejected", "preserved")
def invalid_title():
    temp, app = application()
    try:
        client = app.test_client()
        login(client)
        response = client.post("/create", data={"title": "", "body": "body"})
        assert response.status_code == 200
        with app.app_context():
            assert get_db().execute("SELECT count(*) FROM post").fetchone()[0] == 0
    finally:
        temp.cleanup()


@case("legacy_database_upgrade_is_non_destructive_and_repeatable", "integration")
def legacy_upgrade():
    temp, app = application(old=True)
    try:
        old_id = add_post(app, "legacy")
        with app.app_context():
            db = get_db()
            db.execute("CREATE TABLE audit_note (note TEXT)")
            db.execute("INSERT INTO audit_note VALUES ('retain')")
            db.commit()
            users = [tuple(r) for r in db.execute("SELECT * FROM user ORDER BY id")]
            before = dict(db.execute("SELECT * FROM post WHERE id=?", (old_id,)).fetchone())
        for _ in range(2):
            result = app.test_cli_runner().invoke(args=["upgrade-db"])
            assert result.exit_code == 0, result.output
        with app.app_context():
            db = get_db()
            after = dict(db.execute("SELECT * FROM post WHERE id=?", (old_id,)).fetchone())
            assert after["status"] == "published"
            assert {key: after[key] for key in before} == before
            assert [tuple(r) for r in db.execute("SELECT * FROM user ORDER BY id")] == users
            assert db.execute("SELECT note FROM audit_note").fetchone()[0] == "retain"
        assert b"legacy" in app.test_client().get("/").data
    finally:
        temp.cleanup()


@case("create_default_and_draft_visibility", "new")
def create_visibility():
    temp, app = application()
    try:
        writer, other, anon = app.test_client(), app.test_client(), app.test_client()
        login(writer)
        login(other, "other")
        writer.post("/create", data={"title": "public-marker", "body": "body"})
        assert post_row(app, "public-marker")["status"] == "published"
        response = writer.post("/create", data={"title": "private-marker", "body": "body", "status": "draft"})
        assert response.status_code == 302
        assert post_row(app, "private-marker")["status"] == "draft"
        assert b"private-marker" in writer.get("/").data
        assert b"private-marker" not in other.get("/").data
        assert b"private-marker" not in anon.get("/").data
        assert b"public-marker" in anon.get("/").data
    finally:
        temp.cleanup()


@case("editing_draft_preserves_status_and_can_publish", "integration")
def update_visibility():
    temp, app = application()
    try:
        identity = add_post(app, "draft-start", status="draft")
        client = app.test_client()
        login(client)
        client.post(f"/{identity}/update", data={"title": "draft-edited", "body": "body"})
        assert post_row(app, "draft-edited")["status"] == "draft"
        client.post(f"/{identity}/update", data={"title": "now-public", "body": "body", "status": "published"})
        assert post_row(app, "now-public")["status"] == "published"
        assert b"now-public" in app.test_client().get("/").data
    finally:
        temp.cleanup()


@case("invalid_status_never_mutates_data", "integration")
def invalid_status():
    temp, app = application()
    try:
        client = app.test_client()
        login(client)
        client.post("/create", data={"title": "invalid-new", "body": "body", "status": "invalid"})
        assert post_row(app, "invalid-new") is None
        identity = add_post(app, "keep-title", status="published")
        client.post(f"/{identity}/update", data={"title": "lost-title", "body": "changed", "status": "invalid"})
        assert post_row(app, "keep-title")["status"] == "published"
        assert post_row(app, "lost-title") is None
    finally:
        temp.cleanup()


@case("forms_expose_status_and_author_boundaries_survive", "new")
def forms_and_auth():
    temp, app = application()
    try:
        identity = add_post(app, "owned-draft", status="draft")
        client = app.test_client()
        login(client)
        for url in ("/create", f"/{identity}/update"):
            html = client.get(url).data.decode()
            assert 'name="status"' in html or "name='status'" in html
            assert "draft" in html and "published" in html
        index = client.get("/").data.decode()
        assert "draft" in index.lower() or "草稿" in index
        other = app.test_client()
        login(other, "other")
        assert other.get(f"/{identity}/update").status_code == 403
        assert other.post(f"/{identity}/delete").status_code == 403
    finally:
        temp.cleanup()


for name, kind, fn in definitions:
    if mode != "all" and mode != kind:
        continue
    try:
        fn()
        checks.append({"id": name, "kind": kind, "passed": True})
    except Exception as error:
        checks.append({"id": name, "kind": kind, "passed": False,
                       "error": f"{type(error).__name__}: {error}"})
print(json.dumps({"checks": checks, "passed": sum(c["passed"] for c in checks), "total": len(checks)}))
raise SystemExit(0 if all(c["passed"] for c in checks) else 1)
