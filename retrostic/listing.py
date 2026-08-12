"""Parse Retrostic's search results, and build its URLs back up safely.

Retrostic renders search hits as a plain server-side `<table>`, one `<tr>`
per ROM, so this is an HTML parse rather than an API read. It uses
`html.parser` from the standard library rather than a regex over the markup:
a row here legitimately contains nested `<p>`, `<img>` and a repeated
`<a href>` for the same ROM in three responsive variants, and a regex that
survives that today breaks the first time a wrapper element moves.

**Nothing built here is trusted because it came from the page.** Every path
must match `ROM_PATH` before it becomes a URL, which is what keeps a
crafted `href` from turning into a request somewhere else. The allowlist in
`netpolicy` would refuse a foreign host anyway, but a parser that hands the
allowlist something to reject is relying on the last line of defence for
ordinary correctness.

`ROM_PATH` is tight on purpose and the tightness is measured, not hopeful:
all **83,797** ROM URLs in Retrostic's published sitemaps (`roms1.xml` +
`roms2.xml`, surveyed 2026-08-12) use only `[a-z0-9-]` in both the console
and the title slug, and **every one** ends in `-<digits>`. So requiring that
shape rejects nothing real, and the trailing number is a stable per-ROM id
rather than a coincidence of naming.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

BASE = "https://www.retrostic.com"

#: `<console>/<title-slug>-<id>` -- the part of a detail URL after `/roms/`.
#: Anchored, lowercase-only, and the id must be the trailing digits.
ROM_PATH = re.compile(r"([a-z0-9][a-z0-9-]*)/([a-z0-9][a-z0-9-]*-(\d+))")

#: A region tag in the title: "Contra (USA)", "Puyo Pop Fever (J)(M2)".
#: Only the first parenthesised group is taken -- the rest are dump flags.
_REGION = re.compile(r"\(([^)]{1,24})\)")

_HREF = re.compile(r"^/roms/(.+?)/?$")


@dataclass(frozen=True)
class Entry:
    """One search hit, already validated into parts that rebuild a URL."""

    path: str          # "nes/contra-388" -- this is the source_id
    console: str       # "nes" -- Retrostic's console slug
    rom_id: str        # "388"
    title: str         # "Contra (USA)"
    console_label: str = ""   # "NES" as the table printed it
    downloads: int | None = None

    @property
    def page_url(self) -> str:
        return f"{BASE}/roms/{self.path}"

    @property
    def play_url(self) -> str:
        return f"{BASE}/roms/{self.path}/play"

    @property
    def region(self) -> str:
        match = _REGION.search(self.title)
        return match.group(1).strip() if match else ""


def split_path(value: str) -> tuple[str, str, str] | None:
    """`"nes/contra-388"` -> `("nes/contra-388", "nes", "388")`, or nothing.

    The single gate every path passes through, whether it arrived from a
    parsed page or from a `SearchResult.source_id` handed back by the host
    on a later call. `fullmatch` rather than `search`, so a path with
    anything appended -- `../`, a query, a second segment -- is not a match
    at all rather than a match with a tail.
    """
    text = str(value or "").strip().strip("/").casefold()
    found = ROM_PATH.fullmatch(text)
    return (text, found.group(1), found.group(3)) if found else None


def _as_int(text: str) -> int | None:
    digits = re.sub(r"[^0-9]", "", text or "")
    return int(digits) if digits else None


class _Row:
    __slots__ = ("href", "anchor_texts", "plain_texts")

    def __init__(self) -> None:
        self.href: str | None = None
        #: Text inside an `<a>` pointing at this row's ROM -- i.e. the title,
        #: in each of the responsive variants the row renders.
        self.anchor_texts: list[str] = []
        #: Text in cells that hold no such anchor -- the console label and
        #: the download count.
        self.plain_texts: list[str] = []


class _ResultTableParser(HTMLParser):
    """Collect `<tr>` rows, keeping anchor text apart from plain cell text.

    That separation is the whole trick, and it is not cosmetic. Retrostic
    prints each hit three times per row for its responsive breakpoints:

        <td>  <a href="/roms/nes/contra-388"><p>Contra (USA) for NES</p></a>
        <td>  <a href="/roms/nes/contra-388"><img ...></a>
        <td>  <a href="/roms/nes/contra-388">Contra (USA)</a>
        <td>  NES
        <td>  127251

    The **title is anchor text**; the **console label is not**. An earlier
    version of this parser flattened the row to a list of cell strings and
    picked the shortest as the title, which cheerfully returned "NES" --
    every ROM in the library named after its console. Reading the structure
    the markup actually has is both simpler and correct, and it does not
    depend on which `<td>` index anything sits at, so a breakpoint being
    added or dropped upstream changes nothing here.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[_Row] = []
        self._row: _Row | None = None
        self._buf: list[str] = []
        self._in_cell = False
        self._anchor_depth = 0
        self._anchor_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = _Row()
        elif self._row is None:
            return
        elif tag in ("td", "th"):
            self._in_cell, self._buf = True, []
        elif tag == "a":
            href = dict(attrs).get("href") or ""
            found = _HREF.match(href.strip())
            path = split_path(found.group(1)) if found else None
            # Only anchors for *this* row's ROM count. A "related games"
            # link inside the row would otherwise contribute a title.
            if path and (self._row.href is None or path[0] == self._row.href):
                self._row.href = path[0]
                self._anchor_depth += 1
                self._anchor_buf = []

    def handle_endtag(self, tag: str) -> None:
        if self._row is None:
            return
        if tag == "a" and self._anchor_depth:
            self._anchor_depth -= 1
            if not self._anchor_depth:
                text = " ".join("".join(self._anchor_buf).split())
                if text:
                    self._row.anchor_texts.append(text)
                self._anchor_buf = []
        elif tag in ("td", "th") and self._in_cell:
            text = " ".join("".join(self._buf).split())
            # A cell that contained an anchor has already contributed its
            # text as anchor text; recording it again here would let the
            # mobile variant masquerade as a plain label.
            if text and not any(text == a or text.endswith(a) for a in self._row.anchor_texts):
                self._row.plain_texts.append(text)
            self._in_cell, self._buf = False, []
        elif tag == "tr":
            if self._row.href:
                self.rows.append(self._row)
            self._row = None
            self._in_cell, self._anchor_depth = False, 0

    def handle_data(self, data: str) -> None:
        if self._anchor_depth:
            self._anchor_buf.append(data)
        if self._in_cell:
            self._buf.append(data)


def parse_search(markup: str) -> list[Entry]:
    """Every ROM on one search-results page, in the order it was rendered.

    Rows that do not carry a valid ROM path are skipped rather than raised
    on: the same table markup wraps the header row and the site's own
    navigation, and a search that legitimately found nothing must come back
    empty rather than as a failure.
    """
    parser = _ResultTableParser()
    parser.feed(markup or "")
    parser.close()

    out: list[Entry] = []
    seen: set[str] = set()
    for row in parser.rows:
        parts = split_path(row.href or "")
        if parts is None or parts[0] in seen:
            continue
        path, console, rom_id = parts
        seen.add(path)

        # Among the responsive variants the shortest is the clean title: the
        # mobile one appends " for <Console>" to the same string.
        title = min(row.anchor_texts, key=len) if row.anchor_texts else ""
        if not title:
            continue

        labels = [t for t in row.plain_texts if not t.isdecimal()]
        numbers = [t for t in row.plain_texts if t.isdecimal()]
        out.append(Entry(
            path=path,
            console=console,
            rom_id=rom_id,
            title=title,
            console_label=labels[0] if labels else "",
            downloads=_as_int(numbers[-1]) if numbers else None,
        ))
    return out


def next_page_url(query: str, page: int) -> str:
    """Retrostic's own pagination shape: `?currentpage=N&search_term_string=`.

    Page 1 omits `currentpage`, exactly as the site's first page does, so a
    single-page search sends the request the site itself would have sent.
    """
    from urllib.parse import urlencode

    params = {"search_term_string": query}
    if page > 1:
        params = {"currentpage": page, "search_term_string": query}
    return f"{BASE}/search?{urlencode(params)}"
