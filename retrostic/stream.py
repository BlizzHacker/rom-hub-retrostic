"""Resolve a search hit to Retrostic's own hosted player page.

Every ROM in the catalogue has one: `/roms/<console>/<slug>/play` returns
200 and renders the site's player. So unlike the Vimm plugin -- which has to
check whether a "Play Online" control was captured, because on Vimm only
some entries have one -- there is no per-entry playability flag to consult
here, and inventing one would mean an extra request per resolve to confirm
something that is uniformly true.

What is *not* returned is the target of the iframe inside that page. The
player embeds a direct `.zip` URL on `downloads.retrostic.com`, and handing
that back would turn a "play this" answer into a download link the site did
not offer as one. The page is what Retrostic publishes; the page is what
this returns. `manifest.toml` does not even declare that host, so the
allowlist refuses it independently of this file.
"""

from rom_hub_sdk import SearchResult, StreamProvider, StreamTarget

from .listing import Entry, split_path
from .platforms import platform_for


class StreamRefused(Exception):
    """The id is not a Retrostic ROM path this plugin will build a URL from."""


class Stream(StreamProvider):
    def resolve(self, result: SearchResult) -> StreamTarget:
        source_id = getattr(result, "source_id", "") or ""
        parts = split_path(source_id)
        if parts is None:
            # Re-validated rather than trusted, even though it is our own
            # `source_id` coming back: by the time the host calls resolve()
            # the value has been round-tripped through storage and another
            # process, and the URL built from it is one somebody's browser
            # will open.
            raise StreamRefused(
                f"{source_id!r} is not a Retrostic ROM path of the form "
                "'<console>/<title-slug>-<id>'"
            )
        path, console, rom_id = parts
        platform = platform_for(console)
        if platform is None:
            raise StreamRefused(
                f"Retrostic console {console!r} has no ROMarr platform, so "
                f"{path!r} is not a ROM this plugin answers for"
            )

        entry = Entry(path=path, console=console, rom_id=rom_id,
                      title=result.title or path)
        return StreamTarget(
            kind="url",
            target=entry.play_url,
            mime_type="text/html",
            title=entry.title,
            extra={
                "retrostic_console": console,
                "retrostic_id": rom_id,
                "platform": platform,
                "page_url": entry.page_url,
            },
        )
