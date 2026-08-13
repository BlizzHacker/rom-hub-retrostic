import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ROM Hub's SDK is not on the path when the plugin repo is checked out on its
# own. Look where it lives on the deployment first, then fall back to a
# sibling working copy, so the suite runs both on the server and on a laptop.
for candidate in (
    os.environ.get("ROM_HUB_SRC"),
    "/opt/rom-hub/src",
    str(ROOT.parent / "rom-hub-work" / "src"),
    str(ROOT.parent / "rom-hub" / "src"),
):
    if candidate and Path(candidate).is_dir():
        sys.path.insert(0, candidate)
        break

# Platform mapping tests use ROMarr's canonical registry. Keep this separate
# from ROM Hub's SDK path: the two projects are sibling checkouts in
# development and independent installs in production.
for candidate in (
    os.environ.get("ROMARR_SRC"),
    "/opt/romarr",
    str(ROOT.parent / "romarr-work"),
    str(ROOT.parent / "romarr"),
):
    if candidate and Path(candidate, "romarr").is_dir():
        sys.path.insert(0, candidate)
        break


class FakeHttp:
    """Stands in for `ctx.http`, which is an RPC to the host in production.

    Records every URL so a test can assert not just what came back but how
    many requests it cost -- politeness is a behaviour of this plugin, so it
    has to be assertable.
    """

    def __init__(self, pages):
        # pages: list of (status_code, text), served in order
        self._pages = list(pages)
        self.urls = []

    def get(self, url, params=None):
        self.urls.append(url)
        if not self._pages:
            raise AssertionError(f"unexpected extra request to {url}")
        status, text = self._pages.pop(0)
        return type("R", (), {"status_code": status, "text": text})()


@pytest.fixture
def fixture_dir():
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def search_html(fixture_dir):
    return (fixture_dir / "search_contra.html").read_text(encoding="utf-8")
