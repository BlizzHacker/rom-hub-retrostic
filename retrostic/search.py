"""Search Retrostic through the site's own public search endpoint.

`GET /search?search_term_string=<q>` is what Retrostic's own search box
submits, so a query here costs the site exactly one page render -- the same
one a visitor's search costs. That is why this plugin does not mirror the
catalogue: Retrostic publishes 83,797 ROM URLs across two sitemaps, and
walking them to answer "sonic" would be tens of thousands of requests to
replace one.

(It could not walk them anyway. `roms1.xml` is 4.9 MB and `ctx.http` caps a
response at 4 MiB, so the bulk path is closed as well as impolite. The
sitemaps were still worth reading once, offline -- they are where
`platforms.py`'s table and its ROM counts come from.)

Results whose console has no ROMarr platform are **dropped, not renamed**.
`platform_for` returning nothing is a decision, and honouring it here is
what keeps a BBC Micro disk image out of some other machine's folder.
"""

from __future__ import annotations

import re
import time

from rom_hub_sdk import SearchProvider, SearchResult

from .listing import next_page_url, parse_search
from .platforms import platform_for

#: Retrostic renders 30 hits a page. Knowing this lets a search stop asking
#: for more pages once it has enough, instead of always paying for the cap.
PAGE_SIZE = 30

#: Floor on the configured delay, in milliseconds. An operator can raise the
#: gap between paginated requests but not remove it -- the value exists to be
#: polite to a site that has not asked us for anything, and a configurable
#: zero would quietly turn that off.
MIN_DELAY_MS = 500

#: The default, matching `manifest.toml`. Milliseconds rather than seconds
#: because RPP v1 has no `float` config type -- a manifest declaring one is
#: rejected by `parse_manifest`, so a fractional-second knob has to be an
#: integer count of something smaller.
DEFAULT_DELAY_MS = 1500


def _words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (value or "").casefold())


class Search(SearchProvider):
    def search(self, query: str, platform: str | None, limit: int) -> list[SearchResult]:
        limit = max(0, limit)
        text = (query or "").strip()
        if not text or not limit:
            return []

        config = self.ctx.config or {}
        wanted = str(platform or "").strip().casefold()
        try:
            max_pages = max(1, int(config.get("max_pages", 1)))
        except (TypeError, ValueError):
            max_pages = 1
        try:
            delay_ms = max(
                MIN_DELAY_MS, int(config.get("request_delay_ms", DEFAULT_DELAY_MS))
            )
        except (TypeError, ValueError):
            delay_ms = DEFAULT_DELAY_MS
        # `time.sleep` takes seconds; the config is milliseconds only because
        # that is the type the manifest can declare. Converting once here is
        # what keeps the rest of this method from having to remember which
        # unit it is holding -- the two are a factor of 1000 apart and a
        # mix-up either way is silent.
        delay = delay_ms / 1000.0

        results: list[SearchResult] = []
        seen: set[str] = set()
        for page in range(1, max_pages + 1):
            if page > 1:
                # Between requests, never before the first one: a lone
                # search should not sit still for a second and a half to
                # pay for a page it is not going to ask for.
                time.sleep(delay)

            response = self.ctx.http.get(next_page_url(text, page))
            # 403 and 429 are answers, not hiccups. Stopping is the whole
            # response to them -- a retry here is the beginning of routing
            # around a refusal.
            if response.status_code != 200:
                break

            entries = parse_search(response.text)
            for entry in entries:
                mapped = platform_for(entry.console)
                if mapped is None or entry.path in seen:
                    continue
                if wanted and wanted not in (mapped.casefold(), entry.console):
                    continue
                seen.add(entry.path)
                results.append(SearchResult(
                    source_id=entry.path,
                    title=entry.title,
                    platform=mapped,
                    # Retrostic prints "File Size: unknown" for most of its
                    # catalogue and the results table carries no size at
                    # all, so there is nothing honest to put here. None
                    # means unknown; a zero would read as an empty file.
                    size_bytes=None,
                    url=entry.page_url,
                    extra={
                        "region": entry.region,
                        "retrostic_console": entry.console,
                        "retrostic_id": entry.rom_id,
                        "downloads": str(entry.downloads or ""),
                        # Every entry has a play page; none has an import
                        # path. Saying so per-result saves the caller from
                        # discovering it at `stream`/import time.
                        "playable": "true",
                        "downloadable": "false",
                        # The standalone plugin cannot POST a per-render
                        # session token. ROMarr Capture can read the rendered
                        # page in the operator's signed-in browser, so keep
                        # that supported handoff visible to search consumers.
                        "capture_supported": "true",
                        "download_requires_browser": "true",
                    },
                ))
                if len(results) >= limit:
                    return results

            # A short page is the last page. Without this a max_pages of 5
            # against a one-page query costs four pointless requests.
            if len(entries) < PAGE_SIZE:
                break
        return results


def _ranked(results: list[SearchResult], query: str) -> list[SearchResult]:
    """Exact title first, then prefix, then alphabetical. Unused by `search`.

    Kept because Retrostic returns its own relevance order and overriding it
    measurably made "contra" worse -- the site put `Contra (USA)` first and
    a local re-rank pushed BBC Micro's `contract-bridge` variants above it
    on shorter-title ties. Left here, named and unwired, so the next person
    to have the idea can see it was tried.
    """
    terms = " ".join(_words(query))
    return sorted(results, key=lambda r: (
        " ".join(_words(r.title)) != terms,
        not " ".join(_words(r.title)).startswith(terms),
        r.title.casefold(),
    ))
