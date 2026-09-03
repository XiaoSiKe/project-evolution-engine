from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.targets.append(attrs["href"])


class ReadmeTests(unittest.TestCase):
    def test_navigation_targets_exist(self):
        body = (ROOT / "README.md").read_text()
        parser = Links()
        parser.feed(body)
        anchors = [link[1:] for link in parser.targets if link.startswith("#")]
        self.assertTrue(anchors)
        self.assertTrue(set(anchors).issubset(parser.ids))

    def test_local_document_links_resolve(self):
        for path in (ROOT / "README.md", ROOT / "docs/verification.md"):
            body = path.read_text()
            links = re.findall(r"\[[^\]]*\]\(([^)]+)\)", body)
            parser = Links()
            parser.feed(body)
            for raw in links + parser.targets:
                raw = raw.split("#", 1)[0]
                if not raw or "://" in raw or raw.startswith("mailto:"):
                    continue
                target = (path.parent / raw).resolve()
                self.assertTrue(target.is_relative_to(ROOT.resolve()), raw)
                self.assertTrue(target.exists(), raw)


if __name__ == "__main__":
    unittest.main()
