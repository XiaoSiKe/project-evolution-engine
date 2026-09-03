"""Withheld ASGI/SQLite checks for the Datasette CSV extension."""
import asyncio
import csv
import io
import json
from pathlib import Path
import sys
import uuid
from urllib.parse import urlencode, urlsplit

WORK = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(WORK))
import datasette
from datasette.app import Datasette
from datasette.database import Database

assert Path(datasette.__file__).resolve().is_relative_to(WORK), "wrong Datasette import"


async def application(**settings):
    ds = Datasette(memory=True, cors=True, settings={"default_page_size": 2, "max_returned_rows": 2, **settings},
                   config={"databases": {"demo": {"tables": {"people": {"label_column": "name"}}}}})
    db = Database(ds, memory_name="evolution_" + uuid.uuid4().hex)
    ds.add_database(db, name="demo")
    await db.execute_write_script("""
        create table people(id integer primary key, name text);
        insert into people values(1, 'label'), (2, '');
        create table items(id integer primary key, value text, n integer, who integer references people(id));
        insert into items values(1, null, 0, null), (2, '', 0, 1), (3, 'text', 1, 2), (4, null, 5, null);
        create table binary_items(id integer primary key, value text, data blob);
        insert into binary_items values(1, null, x'0102');
    """)
    await ds.invoke_startup()
    return ds


def rows(response):
    assert response.status_code == 200, response.text[:300]
    return list(csv.reader(io.StringIO(response.text)))


async def default_and_json():
    ds = await application()
    basic = await ds.client.get("/demo/items.csv")
    assert rows(basic) == [["id", "value", "n", "who"], ["1", "", "0", ""], ["2", "", "0", "1"]]
    blank = await ds.client.get("/demo/items.csv?_null=")
    assert blank.text == basic.text
    before = await ds.client.get("/demo/items.json?_shape=array")
    after = await ds.client.get("/demo/items.json?_shape=array&_null=NONE")
    assert before.json() == after.json()
    assert before.json()[0]["value"] is None


async def table_null_and_falsy():
    ds = await application()
    result = rows(await ds.client.get("/demo/items.csv?_null=NONE"))
    assert result[1] == ["1", "NONE", "0", "NONE"]
    assert result[2] == ["2", "", "0", "1"]


async def custom_sql():
    ds = await application()
    query = urlencode({"sql": "select null as missing, '' as empty, 0 as zero union all select 'value', 'x', 1", "_null": "NULL"})
    result = rows(await ds.client.get("/demo/-/query.csv?" + query))
    assert result == [["missing", "empty", "zero"], ["NULL", "", "0"], ["value", "x", "1"]]


async def streamed_pages_and_headers():
    ds = await application()
    result = rows(await ds.client.get("/demo/items.csv?_stream=1&_header=off&_null=NONE"))
    assert len(result) == 4
    assert result[0] == ["1", "NONE", "0", "NONE"]
    assert result[-1] == ["4", "NONE", "5", "NONE"]


async def labels():
    ds = await application()
    result = rows(await ds.client.get("/demo/items.csv?_stream=1&_labels=1&_null=NONE"))
    assert result[0] == ["id", "value", "n", "who", "who_label"]
    assert result[1] == ["1", "NONE", "0", "NONE", "NONE"]
    assert result[2] == ["2", "", "0", "1", "label"]
    assert result[3] == ["3", "text", "1", "2", ""]


async def quoting_unicode_and_trace():
    ds = await application()
    marker = '空,"x"\n</textarea><script>probe</script>'
    query = urlencode({"_null": marker})
    result = rows(await ds.client.get("/demo/items.csv?" + query))
    assert result[1][1] == marker and result[1][3] == marker
    traced = await ds.client.get("/demo/items.csv?_trace=1&" + query)
    assert traced.status_code == 200
    assert "<script>probe</script>" not in traced.text
    assert "&lt;script&gt;probe&lt;/script&gt;" in traced.text


async def downloads_cors_and_blobs():
    ds = await application()
    before = await ds.client.get("/demo/binary_items.csv?_dl=1")
    after = await ds.client.get("/demo/binary_items.csv?_dl=1&_null=NONE")
    assert after.headers["content-disposition"] == before.headers["content-disposition"]
    assert after.headers["content-type"] == before.headers["content-type"]
    assert after.headers["access-control-allow-origin"] == "*"
    before_rows, after_rows = rows(before), rows(after)
    assert before_rows[1][2] == after_rows[1][2] and before_rows[1][2]
    assert after_rows[1][1] == "NONE"
    target = urlsplit(after_rows[1][2])
    blob = await ds.client.get(target.path + ("?" + target.query if target.query else ""))
    assert blob.status_code == 200 and blob.content == b"\x01\x02"


async def stream_guard_preserved():
    ds = await application(allow_csv_stream=False)
    old = await ds.client.get("/demo/items.csv?_stream=1")
    new = await ds.client.get("/demo/items.csv?_stream=1&_null=NONE")
    assert old.status_code == new.status_code == 400
    ds2 = await application()
    a = await ds2.client.get("/demo/items.csv?_stream=1&_next=2")
    b = await ds2.client.get("/demo/items.csv?_stream=1&_next=2&_null=NONE")
    assert a.status_code == b.status_code == 400


async def main():
    checks = []
    for name, kind, function in [
        ("default_empty_marker_and_json_preserved", "preserved", default_and_json),
        ("table_null_without_replacing_falsy_values", "new", table_null_and_falsy),
        ("custom_sql_uses_the_same_null_rule", "integration", custom_sql),
        ("stream_all_pages_without_header", "integration", streamed_pages_and_headers),
        ("expanded_null_and_empty_foreign_labels", "integration", labels),
        ("csv_quoting_unicode_and_html_trace", "integration", quoting_unicode_and_trace),
        ("download_cors_and_blob_paths", "integration", downloads_cors_and_blobs),
        ("stream_guards_preserved", "preserved", stream_guard_preserved),
    ]:
        try:
            await function()
            checks.append({"id": name, "kind": kind, "passed": True})
        except Exception as error:
            checks.append({"id": name, "kind": kind, "passed": False, "error": f"{type(error).__name__}: {error}"})
    print(json.dumps({"checks": checks, "passed": sum(c["passed"] for c in checks), "total": len(checks)}))
    return 0 if all(c["passed"] for c in checks) else 1


raise SystemExit(asyncio.run(main()))
