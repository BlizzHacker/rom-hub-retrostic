"""Retrostic console slug -> RomM/ROMarr platform slug.

Exact-match lookup, no fallback and no prefix rules. A console that is not
spelled out below resolves to nothing and its results are dropped, because
the alternative -- guessing -- files a ROM into another machine's directory
and nothing afterwards says anything went wrong.

**Every value here was checked against ROMarr's own table**, not written
from memory: each one was passed through `romarr.platforms.resolve()` and
had to come back as the platform whose `.slug` is that exact string.
`tests/test_platforms.py` re-runs that check whenever `romarr` is
importable, so a slug cannot be invented later either.

The keys are the 44 console slugs Retrostic publishes in
`sitemaps/consoles.xml`, and the counts in the comments are its own ROM
counts from `sitemaps/roms1.xml` + `roms2.xml` (83,797 URLs total, surveyed
2026-08-12). They are the real distribution rather than a sample, which is
what makes the two omissions below measurable instead of vague.

**Two consoles are deliberately unmapped.**

* `bbc-micro` (4,753 ROMs). ROMarr has no BBC Micro platform. There is
  nothing to map it to, so it is counted and skipped -- the same answer the
  Vimm plugin gives for a system RomM does not carry.

* `neo-geo` (357 ROMs). This one is a *choice*, not a gap, and it is the
  more interesting of the two. ROMarr carries `neogeoaes` (the home
  cartridge machine), `neogeomvs` (the arcade board) and `arcade`, and
  Retrostic's console slug says only "neo-geo". The files are MAME-style
  romsets, which is evidence for MVS; they sit in a consumer ROM catalogue
  next to Game Boy and SNES, which is evidence for AES. Two plausible slugs
  and no way to choose between them from the metadata is exactly the case
  for refusing to answer. Mapping it to `arcade` would dodge the question
  rather than settle it, since that is a third answer and not obviously the
  right one either.

The arcade collapse below is *not* that same case, and the difference is
worth being explicit about. `cps-1`, `cps-2`, `cps-3`, `mame` and `naomi`
all map to `arcade` because ROMarr models arcade hardware as one platform:
Capcom Play System and Sega NAOMI *are* arcade boards, and the distinction
between them is which emulator core loads the romset, not which library
folder holds it. Neo Geo is different precisely because ROMarr does draw a
line there and gives it two sides.

Two Retrostic consoles mapping to one ROMarr slug is ordinary and expected
-- `c64-preservation` and `c64-tapes` are one machine under two curation
styles, and `famicom`/`nes` are one family ROMarr does keep apart, so those
two get their own slugs.
"""

#: Retrostic console slug -> ROMarr platform slug. Counts are Retrostic's.
PLATFORMS: dict[str, str] = {
    "3do": "3do",                                   # 3
    "atari-2600": "atari2600",                      # 618
    "atari-5200": "atari5200",                      # 94
    "atari-7800": "atari7800",                      # 59
    "atari-jaguar": "jaguar",                       # 62
    "atari-lynx": "lynx",                           # 86
    "atari-st": "atari-st",                         # 8,368
    "c64-preservation": "c64",                      # 1,667
    "c64-tapes": "c64",                             # 1,683
    "cd-i": "philips-cd-i",                         # 44
    "cps-1": "arcade",                              # 136
    "cps-2": "arcade",                              # 239
    "cps-3": "arcade",                              # 8
    "dreamcast": "dc",                              # 4
    "famicom": "famicom",                           # 145
    "game-gear": "gamegear",                        # 454
    "gamecube": "ngc",                              # 153
    "gb": "gb",                                     # 1,527
    "gba": "gba",                                   # 2,668
    "gbc": "gbc",                                   # 1,335
    "mame": "arcade",                               # 33,821
    "master-system": "sms",                         # 484
    "megadrive": "genesis-slash-megadrive",         # 1,523
    "n64": "n64",                                   # 835
    "naomi": "arcade",                              # 74
    "nds": "nds",                                   # 6,457
    "neo-geo-pocket": "neo-geo-pocket",             # 76
    "nes": "nes",                                   # 2,584
    "ps-1": "psx",                                  # 845
    "ps-2": "ps2",                                  # 155
    "ps-3": "ps3",                                  # 18
    "psp": "psp",                                   # 300
    "saturn": "saturn",                             # 349
    "sega-32x": "sega32",                           # 38
    "sharp-x68000": "sharp-x68000",                 # 3,244
    "snes": "snes",                                 # 3,973
    "turbografx16": "turbografx16--1",              # 624
    "virtual-boy": "virtualboy",                    # 25
    "wii": "wii",                                   # 70
    "wonderswan": "wonderswan",                     # 145
    "wonderswan-color": "wonderswan-color",         # 90
    "zx-spectrum": "zxs",                           # 3,604
}

#: Consoles Retrostic has that this plugin will not answer for, with the ROM
#: count each one costs and why. Kept as data rather than prose so
#: `tests/test_platforms.py` can assert the two sets do not overlap and that
#: together they account for all 44 published consoles.
UNMAPPED: dict[str, str] = {
    "bbc-micro": "ROMarr has no BBC Micro platform (4,753 ROMs)",
    "neo-geo": (
        "ambiguous between ROMarr's neogeoaes and neogeomvs; the metadata "
        "does not decide it (357 ROMs)"
    ),
}


def platform_for(console_slug: str) -> str | None:
    """The ROMarr slug for a Retrostic console, or nothing.

    Nothing is a real answer here and callers treat it as one: `search`
    drops the result rather than emitting it under a guessed platform.
    """
    return PLATFORMS.get(str(console_slug or "").strip().casefold())
