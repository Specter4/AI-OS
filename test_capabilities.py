import pytest

from workflow.capabilities import CapabilityRegistry, CapabilitySpec


def test_register_and_lookup_capability_case_insensitively():
    registry = CapabilityRegistry()
    capability = CapabilitySpec(
        "browser",
        "Navigate and interact with websites",
        "web",
        actions=("open_url", "click", "type"),
    )
    assert registry.register(capability) is capability
    assert registry.get(" BROWSER ") is capability
    assert registry.require("BROWSER").actions == ("open_url", "click", "type")


def test_discover_matches_name_description_category_and_actions():
    registry = CapabilityRegistry()
    browser = CapabilitySpec("browser", "Navigate websites", "web", actions=("click",))
    filesystem = CapabilitySpec("filesystem", "Read and write files", "computer", actions=("read_file",))
    registry.register(browser)
    registry.register(filesystem)

    assert registry.discover("website") == (browser,)
    assert registry.discover("computer") == (filesystem,)
    assert registry.discover("read_file") == (filesystem,)
    assert registry.discover("web", category="web") == (browser,)


def test_disabled_capabilities_are_not_discoverable_but_remain_registered():
    registry = CapabilityRegistry()
    capability = CapabilitySpec("browser", "Navigate websites", "web", enabled=False)
    registry.register(capability)

    assert registry.get("browser") is capability
    assert registry.discover("browser") == ()
    assert registry.list(enabled_only=False) == (capability,)
    assert registry.list(enabled_only=True) == ()


def test_empty_query_discovers_all_enabled_capabilities():
    registry = CapabilityRegistry()
    first = CapabilitySpec("browser", "Browse", "web")
    second = CapabilitySpec("filesystem", "Files", "computer")
    disabled = CapabilitySpec("email", "Email", "communication", enabled=False)
    for item in (first, second, disabled):
        registry.register(item)

    assert registry.discover() == (first, second)


def test_duplicate_or_empty_capability_names_are_rejected():
    registry = CapabilityRegistry()
    registry.register(CapabilitySpec("browser", "Browse", "web"))
    with pytest.raises(ValueError):
        registry.register(CapabilitySpec(" BROWSER ", "Duplicate", "web"))
    with pytest.raises(ValueError):
        registry.register(CapabilitySpec("   ", "Invalid", "web"))


def test_unknown_capability_is_explicitly_rejected_and_clear_works():
    registry = CapabilityRegistry()
    assert registry.get("missing") is None
    with pytest.raises(KeyError):
        registry.require("missing")

    registry.register(CapabilitySpec("browser", "Browse", "web"))
    registry.clear()
    assert registry.names() == ()
