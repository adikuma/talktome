from talktome import registry


# clear state between tests
def setup_function():
    registry.agents.clear()


def test_register_creates_entry():
    entry = registry.register("backend", "/home/user/api")
    assert entry["name"] == "backend"
    assert entry["path"] == "/home/user/api"
    assert entry["status"] == "active"
    assert entry["metadata"] == {}
    assert "registered_at" in entry
    assert "last_seen" in entry


def test_register_with_metadata():
    entry = registry.register("backend", "/api", metadata={"lang": "python"})
    assert entry["metadata"] == {"lang": "python"}


def test_register_overwrites_existing():
    registry.register("backend", "/old/path")
    entry = registry.register("backend", "/new/path")
    assert entry["path"] == "/new/path"
    assert registry.count() == 1


def test_deregister_removes_agent():
    registry.register("backend", "/api")
    assert registry.deregister("backend") is True
    assert registry.is_registered("backend") is False


def test_deregister_returns_false_if_not_found():
    assert registry.deregister("nonexistent") is False


def test_get_returns_entry():
    registry.register("backend", "/api")
    entry = registry.get("backend")
    assert entry is not None
    assert entry["name"] == "backend"


def test_get_returns_none_if_not_found():
    assert registry.get("nonexistent") is None


def test_list_all_returns_all_names():
    registry.register("backend", "/api")
    registry.register("frontend", "/web")
    result = registry.list_all()
    assert "backend" in result
    assert "frontend" in result
    assert len(result) == 2


def test_list_all_empty():
    assert registry.list_all() == []


def test_update_status():
    registry.register("backend", "/api")
    assert registry.update_status("backend", "idle") is True
    assert registry.get("backend")["status"] == "idle"


def test_update_status_returns_false_if_not_found():
    assert registry.update_status("nonexistent", "idle") is False


def test_update_metadata():
    registry.register("backend", "/api")
    assert registry.update_metadata("backend", {"lang": "python"}) is True
    assert registry.get("backend")["metadata"] == {"lang": "python"}


def test_update_metadata_returns_false_if_not_found():
    assert registry.update_metadata("nonexistent", {}) is False


def test_is_registered():
    registry.register("backend", "/api")
    assert registry.is_registered("backend") is True
    assert registry.is_registered("nonexistent") is False


def test_count():
    assert registry.count() == 0
    registry.register("backend", "/api")
    assert registry.count() == 1
    registry.register("frontend", "/web")
    assert registry.count() == 2
