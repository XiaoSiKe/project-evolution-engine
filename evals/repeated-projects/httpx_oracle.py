"""Withheld public-interface checks for the HTTPX update."""
import asyncio
import json
from pathlib import Path
import sys

WORK = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(WORK))
import httpx

assert Path(httpx.__file__).resolve().is_relative_to(WORK), "wrong HTTPX import"
TEXTS = ["", "\n", "\r", "\r\n", "a\r\nb\rc\n\r", "汉字\r\n🙂\n尾", "a\v\f\x1c\x1d\x1e\x85\u2028\u2029z", "tail", "\r\r", "a\n\n"]


class SyncChunks(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks, self.visited, self.closed = chunks, 0, False

    def __iter__(self):
        for chunk in self.chunks:
            self.visited += 1
            yield chunk

    def close(self):
        self.closed = True


class AsyncChunks(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks, self.visited, self.closed = chunks, 0, False

    async def __aiter__(self):
        for chunk in self.chunks:
            self.visited += 1
            yield chunk

    async def aclose(self):
        self.closed = True


def sync_default():
    for text in TEXTS:
        assert list(httpx.Response(200, content=text.encode()).iter_lines()) == text.splitlines()


async def async_default():
    for text in TEXTS:
        r = httpx.Response(200, stream=AsyncChunks([text.encode()]))
        assert [line async for line in r.aiter_lines()] == text.splitlines()


def cached_keepends():
    for text in TEXTS:
        for keep in (False, True):
            response = httpx.Response(200, content=text.encode())
            assert list(response.iter_lines(keepends=keep)) == text.splitlines(keepends=keep)
            assert response.text == text


def sync_boundaries():
    for text in TEXTS:
        raw = text.encode()
        for index in range(len(raw) + 1):
            for keep in (False, True):
                stream = SyncChunks([raw[:index], b"", raw[index:]])
                response = httpx.Response(200, stream=stream)
                assert list(response.iter_lines(keepends=keep)) == text.splitlines(keepends=keep), (text, index, keep)
                assert stream.closed and response.is_closed and response.is_stream_consumed


async def async_boundaries():
    for text in TEXTS:
        raw = text.encode()
        for index in range(len(raw) + 1):
            for keep in (False, True):
                stream = AsyncChunks([raw[:index], b"", raw[index:]])
                response = httpx.Response(200, stream=stream)
                assert [line async for line in response.aiter_lines(keepends=keep)] == text.splitlines(keepends=keep), (text, index, keep)
                assert stream.closed and response.is_closed and response.is_stream_consumed


def sync_incremental():
    stream = SyncChunks([b"first\n", b"later\n"])
    response = httpx.Response(200, stream=stream)
    iterator = response.iter_lines(keepends=True)
    assert next(iterator) == "first\n"
    assert stream.visited == 1, "must not consume the entire stream before returning a complete line"
    assert list(iterator) == ["later\n"]


async def async_incremental():
    stream = AsyncChunks([b"first\n", b"later\n"])
    response = httpx.Response(200, stream=stream)
    iterator = response.aiter_lines(keepends=True)
    assert await anext(iterator) == "first\n"
    assert stream.visited == 1
    assert [line async for line in iterator] == ["later\n"]


async def cached_async_and_other_interfaces():
    for text in TEXTS:
        response = httpx.Response(200, content=text.encode())
        assert [line async for line in response.aiter_lines(keepends=True)] == text.splitlines(keepends=True)
        assert "".join(response.iter_text()) == text
        assert response.content == text.encode()


checks = []
for name, kind, function in [
    ("sync_default_preserved", "preserved", sync_default),
    ("async_default_preserved", "preserved", async_default),
    ("cached_keepends", "new", cached_keepends),
    ("sync_arbitrary_chunk_boundaries_and_close", "integration", sync_boundaries),
    ("async_arbitrary_chunk_boundaries_and_close", "integration", async_boundaries),
    ("sync_incremental_delivery", "integration", sync_incremental),
    ("async_incremental_delivery", "integration", async_incremental),
    ("cached_async_and_other_interfaces", "integration", cached_async_and_other_interfaces),
]:
    try:
        result = function()
        if asyncio.iscoroutine(result):
            asyncio.run(result)
        checks.append({"id": name, "kind": kind, "passed": True})
    except Exception as error:
        checks.append({"id": name, "kind": kind, "passed": False, "error": f"{type(error).__name__}: {error}"})
print(json.dumps({"checks": checks, "passed": sum(c["passed"] for c in checks), "total": len(checks)}))
raise SystemExit(0 if all(c["passed"] for c in checks) else 1)
