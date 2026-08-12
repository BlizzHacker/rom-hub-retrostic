import pytest

from retrostic.listing import Entry, next_page_url, parse_search, split_path


def test_parses_every_real_row(search_html):
    entries = parse_search(search_html)
    assert [e.path for e in entries] == [
        "nes/contra-388",
        "gb/contra-spirits-14639",
        "c64-preservation/contra-30631",
        "bbc-micro/contraption-bootfile-ssd-18316",
        "neo-geo/contra-clone-9001",
    ]


def test_prefers_the_clean_title_over_the_mobile_variant(search_html):
    # The mobile cell renders "Contra (USA) for NES"; the wide cell renders
    # "Contra (USA)". Picking the wrong one puts the console name into every
    # title in the library.
    first = parse_search(search_html)[0]
    assert first.title == "Contra (USA)"
    assert first.console_label == "NES"
    assert first.downloads == 127251


def test_splits_console_and_id(search_html):
    first = parse_search(search_html)[0]
    assert (first.console, first.rom_id) == ("nes", "388")


def test_region_comes_from_the_first_parenthesised_group():
    assert Entry("nes/x-1", "nes", "1", "Contra (USA)").region == "USA"
    # Dump flags follow the region; only the first group is the region.
    assert Entry("nds/y-2", "nds", "2", "Puyo Pop Fever (J)(M2)").region == "J"
    assert Entry("nes/z-3", "nes", "3", "Contraption").region == ""


def test_urls_are_built_from_the_validated_path():
    entry = Entry("nes/contra-388", "nes", "388", "Contra (USA)")
    assert entry.page_url == "https://www.retrostic.com/roms/nes/contra-388"
    assert entry.play_url == "https://www.retrostic.com/roms/nes/contra-388/play"


@pytest.mark.parametrize("path", [
    "nes/contra-388",
    "c64-preservation/contra-30631",
    "bbc-micro/contraption-a2-1-contrap-start-ssd-20668",
])
def test_accepts_real_sitemap_shapes(path):
    assert split_path(path) is not None


@pytest.mark.parametrize("path", [
    "",
    "nes",                              # no title slug
    "nes/contra",                       # no trailing id
    "nes/contra-388/play",              # a tail is not a match
    "../../etc/passwd",
    "nes/contra-388?x=1",
    "nes/contra-388#frag",
    "https://evil.example/roms/nes/x-1",
    "NES/Contra-388/../../x-1",
])
def test_rejects_anything_that_is_not_exactly_a_rom_path(path):
    assert split_path(path) is None


def test_path_matching_is_anchored_not_a_search():
    # The regex must not find a valid path *inside* a hostile string. This is
    # the check that keeps a crafted href from becoming a URL.
    assert split_path("evil.example/nes/contra-388") is None
    assert split_path("nes/contra-388/../../admin") is None


def test_case_is_folded_so_one_rom_has_one_id():
    assert split_path("NES/Contra-388")[0] == "nes/contra-388"


def test_rows_without_a_rom_link_are_skipped_not_raised_on():
    assert parse_search("<table><tr><th>Game</th><th>Console</th></tr></table>") == []
    assert parse_search("") == []
    assert parse_search("<html><body>no results</body></html>") == []


def test_duplicate_rows_collapse_to_one_entry():
    row = (
        '<tr><td><a href="/roms/nes/contra-388">Contra (USA)</a></td>'
        '<td>NES</td><td>1</td></tr>'
    )
    assert len(parse_search(f"<table>{row}{row}</table>")) == 1


def test_page_one_omits_currentpage():
    # Page 1 must be the request the site's own search box sends.
    assert next_page_url("contra", 1) == (
        "https://www.retrostic.com/search?search_term_string=contra"
    )


def test_later_pages_use_the_sites_own_pagination_shape():
    assert next_page_url("contra", 2) == (
        "https://www.retrostic.com/search?currentpage=2&search_term_string=contra"
    )


def test_query_is_url_encoded():
    assert "search_term_string=mike+tyson%27s" in next_page_url("mike tyson's", 1)
