import pytest
from conftest import FakeHttp

from rom_hub_sdk import PluginContext

from retrostic.search import PAGE_SIZE, Search
from retrostic.stream import Stream, StreamRefused


def ctx(pages, **config):
    return PluginContext(config=config, http=FakeHttp(pages))


def test_search_maps_platforms_and_drops_the_unmappable(search_html):
    http = FakeHttp([(200, search_html)])
    results = Search(PluginContext(config={}, http=http)).search("contra", None, 20)

    # 5 rows in, 3 out: bbc-micro has no ROMarr platform and neo-geo is
    # deliberately ambiguous. Neither may be emitted under a guessed slug.
    assert [(r.source_id, r.platform) for r in results] == [
        ("nes/contra-388", "nes"),
        ("gb/contra-spirits-14639", "gb"),
        ("c64-preservation/contra-30631", "c64"),
    ]


def test_search_costs_one_request_by_default(search_html):
    http = FakeHttp([(200, search_html)])
    Search(PluginContext(config={}, http=http)).search("contra", None, 20)
    assert http.urls == [
        "https://www.retrostic.com/search?search_term_string=contra"
    ]


def test_search_carries_region_and_ids_without_claiming_a_size(search_html):
    http = FakeHttp([(200, search_html)])
    first = Search(PluginContext(config={}, http=http)).search("contra", None, 5)[0]
    assert first.title == "Contra (USA)"
    assert first.url == "https://www.retrostic.com/roms/nes/contra-388"
    assert first.extra["region"] == "USA"
    assert first.extra["retrostic_id"] == "388"
    assert first.extra["downloadable"] == "false"
    # Retrostic prints "unknown" for most file sizes; None is the honest answer.
    assert first.size_bytes is None


def test_platform_filter_accepts_the_romarr_slug(search_html):
    http = FakeHttp([(200, search_html)])
    results = Search(PluginContext(config={}, http=http)).search("contra", "c64", 20)
    assert [r.source_id for r in results] == ["c64-preservation/contra-30631"]


def test_platform_filter_also_accepts_retrostics_own_console(search_html):
    http = FakeHttp([(200, search_html)])
    results = Search(
        PluginContext(config={}, http=http)
    ).search("contra", "c64-preservation", 20)
    assert [r.source_id for r in results] == ["c64-preservation/contra-30631"]


def test_filtering_to_a_skipped_console_returns_nothing(search_html):
    http = FakeHttp([(200, search_html)])
    assert Search(
        PluginContext(config={}, http=http)
    ).search("contra", "bbc-micro", 20) == []


def test_limit_is_honoured(search_html):
    http = FakeHttp([(200, search_html)])
    assert len(Search(PluginContext(config={}, http=http)).search("contra", None, 1)) == 1


def test_empty_query_makes_no_request():
    http = FakeHttp([])
    assert Search(PluginContext(config={}, http=http)).search("   ", None, 10) == []
    assert http.urls == []


def test_zero_limit_makes_no_request():
    http = FakeHttp([])
    assert Search(PluginContext(config={}, http=http)).search("contra", None, 0) == []
    assert http.urls == []


def test_a_short_page_stops_pagination(search_html):
    # 5 rows is under PAGE_SIZE, so there is no second page to ask for even
    # though max_pages allows three.
    http = FakeHttp([(200, search_html)])
    Search(
        PluginContext(config={"max_pages": 3, "request_delay": 0}, http=http)
    ).search("contra", None, 100)
    assert len(http.urls) == 1


def test_a_full_page_is_followed(search_html, monkeypatch):
    monkeypatch.setattr("retrostic.search.time.sleep", lambda _: None)
    rows = "".join(
        f'<tr><td><a href="/roms/nes/game-{i}">Game {i}</a></td>'
        f"<td>NES</td><td>{i}</td></tr>"
        for i in range(PAGE_SIZE)
    )
    full = f"<table>{rows}</table>"
    http = FakeHttp([(200, full), (200, "<table></table>")])
    Search(
        PluginContext(config={"max_pages": 2, "request_delay": 0}, http=http)
    ).search("game", None, 100)
    assert http.urls == [
        "https://www.retrostic.com/search?search_term_string=game",
        "https://www.retrostic.com/search?currentpage=2&search_term_string=game",
    ]


def test_a_refusal_stops_the_search_rather_than_being_retried():
    # 403 is an answer. Retrying or varying the request is where routing
    # around a refusal would start, so there must be no second request.
    for status in (403, 429, 503, 500):
        http = FakeHttp([(status, "")])
        assert Search(PluginContext(config={}, http=http)).search("x", None, 10) == []
        assert len(http.urls) == 1


def test_paginated_requests_are_spaced(monkeypatch):
    slept = []
    monkeypatch.setattr("retrostic.search.time.sleep", lambda s: slept.append(s))
    rows = "".join(
        f'<tr><td><a href="/roms/nes/game-{i}">Game {i}</a></td><td>NES</td></tr>'
        for i in range(PAGE_SIZE)
    )
    http = FakeHttp([(200, f"<table>{rows}</table>"), (200, "<table></table>")])
    Search(
        PluginContext(config={"max_pages": 2}, http=http)
    ).search("game", None, 100)
    assert slept == [1.5]


def test_the_delay_has_a_floor_an_operator_cannot_configure_away(monkeypatch):
    slept = []
    monkeypatch.setattr("retrostic.search.time.sleep", lambda s: slept.append(s))
    rows = "".join(
        f'<tr><td><a href="/roms/nes/game-{i}">Game {i}</a></td><td>NES</td></tr>'
        for i in range(PAGE_SIZE)
    )
    http = FakeHttp([(200, f"<table>{rows}</table>"), (200, "<table></table>")])
    Search(
        PluginContext(config={"max_pages": 2, "request_delay": 0}, http=http)
    ).search("game", None, 100)
    assert slept == [0.5]


def test_no_delay_before_a_single_page_search(search_html, monkeypatch):
    slept = []
    monkeypatch.setattr("retrostic.search.time.sleep", lambda s: slept.append(s))
    Search(
        PluginContext(config={}, http=FakeHttp([(200, search_html)]))
    ).search("contra", None, 10)
    assert slept == []


def test_garbage_config_falls_back_instead_of_raising(search_html):
    http = FakeHttp([(200, search_html)])
    results = Search(
        PluginContext(config={"max_pages": "lots", "request_delay": "soon"}, http=http)
    ).search("contra", None, 20)
    assert len(results) == 3


# --- stream -----------------------------------------------------------------


def result(source_id, title="Contra (USA)"):
    return type("SR", (), {"source_id": source_id, "title": title})()


def test_stream_returns_retrostics_own_player_page():
    target = Stream(PluginContext(config={}, http=None)).resolve(
        result("nes/contra-388")
    )
    assert target.kind == "url"
    assert target.target == "https://www.retrostic.com/roms/nes/contra-388/play"
    assert target.extra["platform"] == "nes"


def test_stream_never_returns_the_download_host():
    # The play page embeds a direct .zip on downloads.retrostic.com. Handing
    # that back would turn "play" into a download link the site did not offer
    # as one -- and manifest.toml does not declare that host either.
    target = Stream(PluginContext(config={}, http=None)).resolve(
        result("nes/contra-388")
    )
    assert "downloads.retrostic.com" not in target.target


@pytest.mark.parametrize("bad", [
    "", "nes", "../../etc/passwd", "https://evil.example/x",
    "nes/contra-388/../../admin", "evil.example/nes/contra-388",
])
def test_stream_revalidates_the_id_it_is_handed(bad):
    with pytest.raises(StreamRefused):
        Stream(PluginContext(config={}, http=None)).resolve(result(bad))


def test_stream_refuses_a_console_with_no_romarr_platform():
    with pytest.raises(StreamRefused, match="bbc-micro"):
        Stream(PluginContext(config={}, http=None)).resolve(
            result("bbc-micro/contraption-bootfile-ssd-18316")
        )


def test_stream_makes_no_network_request():
    # ctx.http is None here: resolving must be pure URL construction.
    Stream(PluginContext(config={}, http=None)).resolve(result("gb/contra-spirits-14639"))
