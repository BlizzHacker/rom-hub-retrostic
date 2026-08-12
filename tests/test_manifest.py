"""`manifest.toml` is checked here by ROM Hub's own parser, not by eye.

The manifest is the one file in this repo that nothing else exercises. Every
provider test builds a `PluginContext` directly, so a manifest the host flatly
refuses still leaves the suite green -- which is exactly what happened: this
file declared `request_delay = { type = "float" }` for its whole first life,
`float` has never been an RPP v1 config type, and `rom-hub plugin install`
therefore rejected the plugin for everyone while 100 tests passed.

So the parser is imported rather than reimplemented. A local copy of
`SUPPORTED_CONFIG_TYPES` would agree with itself forever and drift away from
the host on the first version that adds or removes a type; importing the real
one means this suite fails the day the host stops accepting something here.
"""

import importlib
import json
from pathlib import Path

import pytest

from rom_hub.manifest import SUPPORTED_CONFIG_TYPES, load_manifest

from retrostic.search import DEFAULT_DELAY_MS, MIN_DELAY_MS

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifest.toml"
CATALOG_PATH = ROOT / "catalog" / "plugins.json"

#: What each declared type has to look like in Python. `bool` is listed
#: before `int` in spirit but checked explicitly in both, because a Python
#: bool *is* an int and `default = true` under `type = "int"` would otherwise
#: pass as the number 1.
_DEFAULT_IS = {
    "str": lambda v: isinstance(v, str),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "bool": lambda v: isinstance(v, bool),
    "list[str]": lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v),
}


@pytest.fixture(scope="module")
def manifest():
    return load_manifest(MANIFEST_PATH)


def test_the_host_can_parse_this_manifest():
    # The whole point of the file. No try/except: a ManifestError raised here
    # is the failure, and its message is word for word what an operator would
    # have read out of a failed `rom-hub plugin install`.
    load_manifest(MANIFEST_PATH)


def test_every_config_type_is_one_rpp_v1_actually_supports(manifest):
    # Implied by the parse above, and stated anyway: this is the assertion
    # that names the class of error, so a future reader sees *why* the parse
    # test exists rather than only that it does.
    for key, spec in manifest.config_schema.items():
        assert spec["type"] in SUPPORTED_CONFIG_TYPES, (
            f"config field {key!r} declares {spec['type']!r}; RPP v1 has "
            f"{sorted(SUPPORTED_CONFIG_TYPES)}"
        )


def test_every_default_is_the_type_it_was_declared_as(manifest):
    # `parse_manifest` checks the type *name* and never the default under it,
    # and `Registry.install` copies these values straight into state.json as
    # the plugin's starting config. So `{ type = "int", default = 1.5 }` is
    # accepted by the host and hands this code a float anyway -- the same bug
    # one level down, and only this test sees it.
    for key, spec in manifest.config_schema.items():
        if "default" not in spec:
            continue
        check = _DEFAULT_IS.get(spec["type"])
        assert check is not None, f"no default check written for {spec['type']!r}"
        assert check(spec["default"]), (
            f"config field {key!r} is declared {spec['type']!r} but defaults "
            f"to {spec['default']!r}"
        )


def test_the_delay_default_is_the_one_the_code_falls_back_to(manifest):
    # Two numbers for one setting: the manifest's seeds state.json at install,
    # the code's is used when that value is missing or unreadable. If they
    # disagree, an unconfigured plugin waits a different length of time than
    # the README and `rom-hub plugin config` both say it does.
    assert manifest.config_schema["request_delay_ms"]["default"] == DEFAULT_DELAY_MS


def test_the_default_delay_is_not_below_its_own_floor(manifest):
    assert manifest.config_schema["request_delay_ms"]["default"] >= MIN_DELAY_MS


def test_every_capability_entrypoint_resolves_to_a_class(manifest):
    # `module:Class` is checked for *shape* by the parser and for existence
    # only when the host spawns the plugin. A renamed class is a manifest
    # that installs cleanly and fails on first use.
    for capability, entrypoint in manifest.capabilities.items():
        module_name, _, attr = entrypoint.partition(":")
        module = importlib.import_module(module_name)
        target = getattr(module, attr, None)
        assert isinstance(target, type), (
            f"capability {capability!r} points at {entrypoint!r}, which is "
            f"not a class in this package"
        )


def test_the_download_host_stays_out_of_the_allowlist(manifest):
    # `downloads.retrostic.com` is where the play page's direct .zip lives.
    # Not declaring it is what makes "no importer" an enforced property
    # rather than a promise -- see README, "Why there is no importer".
    assert "downloads.retrostic.com" not in manifest.network


def test_the_catalog_entry_describes_the_plugin_that_is_here(manifest):
    # ROMarr's Hub → Plugins list is built from catalog/plugins.json, which
    # is a hand-maintained copy of facts that live in manifest.toml. It is
    # read by people deciding whether to install, so it drifting is a
    # correctness problem and not a cosmetic one.
    entry = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["plugins"][0]
    assert entry["slug"] == manifest.slug
    assert entry["version"] == manifest.version
    assert entry["rpp_version"] == manifest.rpp_version
    assert sorted(entry["capabilities"]) == sorted(manifest.capabilities)
    assert sorted(entry["network"]) == sorted(manifest.network)
