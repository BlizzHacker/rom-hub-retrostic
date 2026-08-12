"""The table in platforms.py must not contain a slug somebody invented.

`test_every_slug_is_one_romarr_actually_has` is the load-bearing test in this
repo. A wrong slug does not fail anywhere: the import succeeds, the file
lands, and the library quietly holds a Mega Drive ROM in the Master System
folder. So the mapping is checked against ROMarr's own table rather than
against a copy of it.
"""

import pytest

from retrostic.platforms import PLATFORMS, UNMAPPED, platform_for

romarr_platforms = pytest.importorskip(
    "romarr.platforms",
    reason="ROMarr is not importable here; run in ROMarr's venv to check slugs",
)

#: Retrostic's published console list (sitemaps/consoles.xml, 2026-08-12).
#: Pinned so that a console appearing or disappearing upstream shows up as a
#: failing test rather than as silently missing search results.
PUBLISHED = {
    "cps-1", "cps-2", "cps-3", "nes", "snes", "atari-2600", "atari-5200",
    "atari-7800", "atari-jaguar", "n64", "famicom", "virtual-boy", "3do",
    "turbografx16", "sega-32x", "megadrive", "master-system", "neo-geo",
    "atari-lynx", "wonderswan", "wonderswan-color", "neo-geo-pocket", "gba",
    "gb", "gbc", "game-gear", "bbc-micro", "atari-st", "c64-preservation",
    "c64-tapes", "sharp-x68000", "zx-spectrum", "mame", "nds", "naomi",
    "saturn", "ps-1", "dreamcast", "gamecube", "ps-2", "psp", "ps-3", "wii",
    "cd-i",
}


@pytest.mark.parametrize("console,slug", sorted(PLATFORMS.items()))
def test_every_slug_is_one_romarr_actually_has(console, slug):
    resolved = romarr_platforms.resolve(slug)
    assert resolved is not None, f"{console} -> {slug!r} is not a ROMarr platform"
    # resolve() also answers to names and aliases, so a value that happens to
    # be an alias would pass a bare "is not None". Require the canonical slug.
    assert resolved.slug == slug, (
        f"{console} -> {slug!r} resolves to {resolved.slug!r}, not itself"
    )


def test_the_table_and_the_skips_together_cover_the_published_consoles():
    assert set(PLATFORMS) | set(UNMAPPED) == PUBLISHED


def test_a_console_is_either_mapped_or_skipped_never_both():
    assert not set(PLATFORMS) & set(UNMAPPED)


def test_every_skip_says_why():
    for console, reason in UNMAPPED.items():
        assert len(reason) > 20, f"{console} is skipped without a real reason"


def test_unknown_console_returns_nothing_rather_than_a_guess():
    assert platform_for("bbc-micro") is None
    assert platform_for("neo-geo") is None
    assert platform_for("nintendo-switch") is None
    assert platform_for("") is None
    assert platform_for(None) is None


def test_lookup_folds_case_and_surrounding_space():
    assert platform_for("NES") == "nes"
    assert platform_for(" MegaDrive ") == "genesis-slash-megadrive"
    # Folding is only case and edge whitespace. Inner punctuation is not
    # normalised, so a console slug still has to be the slug.
    assert platform_for("mega drive") is None
    assert platform_for("mega_drive") is None


def test_arcade_collapse_is_deliberate():
    # Five Retrostic consoles are arcade hardware and ROMarr models arcade as
    # one platform. Pinned so nobody "fixes" it into invented slugs.
    assert {platform_for(c) for c in ("cps-1", "cps-2", "cps-3", "mame", "naomi")} == {
        "arcade"
    }


def test_the_two_commodore_curations_are_one_machine():
    assert platform_for("c64-preservation") == platform_for("c64-tapes") == "c64"


def test_famicom_and_nes_stay_apart():
    # ROMarr carries both, so collapsing them would lose a distinction the
    # library is built to keep.
    assert platform_for("famicom") != platform_for("nes")
