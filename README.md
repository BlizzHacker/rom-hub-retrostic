# Retrostic provider for ROM Hub / ROMarr

An RPP v1 provider that searches [Retrostic](https://www.retrostic.com) and
resolves a hit to Retrostic's own hosted player.

| Capability | Status |
|---|---|
| `search` | Implemented — the site's own `GET /search` endpoint |
| `stream` | Implemented — the site's own `/play` page |
| `importer` | **Deliberately absent.** See below |

This is the reference plugin the other MoveWeight ROM-site providers are
modelled on. It was built after a survey of seven sites
(`docs/design/rom-site-survey.md` in the ROMarr repo) and Retrostic was picked
as the one that needs the least from the site and gives the most back.

## Why Retrostic is easy to be a good citizen towards

Its `robots.txt` is `User-agent: * / Disallow:` — everything allowed, no
crawl-delay, no rule naming any agent — and it *publishes* its catalogue:
`sitemaps/consoles.xml` (44 consoles) and `sitemaps/roms.xml` →
`roms1.xml` + `roms2.xml` (**83,797** ROM URLs, surveyed 2026-08-12).

The plugin reads those sitemaps **zero times at runtime**. They were read once,
offline, to build `retrostic/platforms.py` and to check its assumptions against
the whole corpus rather than a sample. At runtime a query costs the site
exactly **one page render** — the same `GET /search?search_term_string=…` its
own search box sends.

That is deliberate on two counts. Mirroring 83,797 pages to answer one query
would be indefensible, and it is also impossible: `roms1.xml` alone is 4.9 MB
and `ctx.http` caps a response at 4 MiB.

## Why the standalone plugin has no importer

Retrostic's download control is a form, not a link:

```html
<form method="post" action="/roms/nes/contra-388/download" id="dl">
  <input type="hidden" name="rom_url"     value="contra-388">
  <input type="hidden" name="console_url" value="nes">
  <input type="hidden" name="session"     value="2511784539">
</form>
```

POST, with a `session` value minted per page render. The standalone ROM Hub
path cannot submit it: `ctx.http` exposes only `get()`, and the host's own
downloader streams `GET` (`rom_hub/importer.py`).

That is not the end of the workflow. ROMarr Capture has a Retrostic detail-page
adapter for the operator's real browser session. It can read the rendered form
and is the correct home for an assisted POST/download handoff. The current
capture endpoint indexes catalogue metadata only, and Retrostic often states
the file size as `unknown`, so those rows remain preview-only until a real size
is present. Search results expose `capture_supported` and
`download_requires_browser` so clients can present that route explicitly.

There **is** a way to make an importer work anyway. The play page embeds a
direct `.zip` URL on `downloads.retrostic.com` inside its emulator iframe, and
lifting that would produce a functioning download path — by going around the
flow the site actually publishes. That is the same call the Vimm.net plugin
made when it declined to forge a `Referer`, and it is declined here too.

So `importer` is **not declared in `manifest.toml`**, rather than declared and
raising at runtime. An operator sees a plugin that does not offer downloads,
not one that offers them and always refuses. `manifest.toml` also does not
declare `downloads.retrostic.com` in its network allowlist, so the enforcement
does not rest on nobody writing the code later.

Every search result carries `downloadable: "false"` in `extra` so callers do
not have to discover this per item.

## Platforms

43 of Retrostic's 44 consoles map to a ROMarr platform. **Every slug in
`retrostic/platforms.py` was checked with `romarr.platforms.resolve()`**, and
`tests/test_platforms.py` re-runs that check whenever ROMarr is importable —
so a slug cannot be invented, and a value that happens to be an alias rather
than a canonical slug fails too.

Two consoles are not answered for:

| Console | ROMs | Why |
|---|---|---|
| `bbc-micro` | 4,753 | ROMarr has no BBC Micro platform. Nothing to map to. |
| `neo-geo` | 357 | ROMarr carries `neogeoaes` *and* `neogeomvs`. The romsets argue for MVS, the catalogue's shelf position argues for AES, and nothing in the metadata settles it. Two plausible slugs is what "refuse to answer" is for. |

Results on those consoles are **dropped**, never emitted under a guessed
platform. `arcade` is a different case and is applied on purpose: `cps-1`,
`cps-2`, `cps-3`, `mame` and `naomi` are all arcade hardware and ROMarr models
arcade as one platform, so the collapse loses nothing the library models.

## Install

```sh
rom-hub plugin install https://git.moveweight.com/BlizzHacker/rom-hub-retrostic --ref v0.1.0
rom-hub search "contra" --platform nes
rom-hub stream retrostic nes/contra-388
```

The `source_id` is the detail path, `<console>/<title-slug>-<id>` — it
reconstructs the URL exactly and is revalidated against an anchored pattern
every time it comes back, including at `stream`, because by then it has been
round-tripped through storage and another process.

To list it in ROMarr's **Hub → Plugins** catalogue:

```sh
rom-hub catalog add moveweight-retrostic \
  https://git.moveweight.com/BlizzHacker/rom-hub-retrostic/raw/tag/v0.1.0/catalog/plugins.json
rom-hub catalog refresh
```

## Config

| Key | Default | Meaning |
|---|---|---|
| `collection` | `Retrostic` | RomM collection name for imported entries |
| `max_pages` | `1` | Result pages per query, 30 hits each |
| `request_delay_ms` | `1500` | Milliseconds between paginated requests, floor `500` |

The delay is in **milliseconds**, and named `_ms`, because RPP v1's config
types are `str | int | bool | list[str] | secret` — there is no `float`,
and `parse_manifest` rejects a manifest that declares one rather than
degrading. An integer count of milliseconds says the same thing in a type
the host actually has. (Worth knowing if you are copying a sibling plugin's
manifest: some of them declare `request_delay = { type = "float" }`, which
does not load.)

`request_delay_ms` has a floor an operator cannot configure away. Retrostic
declares no `Crawl-delay`, so the gap is our own restraint rather than a rule
being followed, and a configurable zero would quietly remove it.

A non-200 — 403, 429, 503 — **stops the search**. It is not retried and the
request is not varied, because that is where routing around a refusal starts.

## Test

```sh
ROM_HUB_SRC=/opt/rom-hub/src PYTHONPATH=/opt/romarr pytest tests/ -q
```

109 passing. `PYTHONPATH` to ROMarr is what makes the platform-slug checks run
rather than skip; without it the suite still passes but the load-bearing test
is skipped, which is the one thing here worth not skipping.

`tests/test_manifest.py` parses `manifest.toml` with ROM Hub's own
`load_manifest` rather than by inspection. Nothing else in the suite touches
the manifest — every provider test builds a `PluginContext` directly — so
before that file existed a manifest the host flatly refused still left all
100 tests green, which is exactly how `request_delay = { type = "float" }`
shipped.

## Terms

Retrostic hosts mixed game content. This provider indexes metadata the site
publishes and links to pages the site presents to visitors; it grants no
redistribution rights and downloads nothing. Operators are responsible for
using it in accordance with applicable law and the source's terms.

## License

MIT — see `LICENSE`.
