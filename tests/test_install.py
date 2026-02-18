import json
import os

import pytest

import talktome


@pytest.fixture
def fake_settings(tmp_path, monkeypatch):
    # use a temp file instead of the real claude settings
    settings_path = str(tmp_path / "settings.json")
    monkeypatch.setattr("talktome.CLAUDE_SETTINGS_PATH", settings_path)
    return settings_path


@pytest.fixture
def fake_claude_json(tmp_path, monkeypatch):
    # use a temp file instead of the real .claude.json
    claude_json_path = str(tmp_path / ".claude.json")
    monkeypatch.setattr("talktome.CLAUDE_JSON_PATH", claude_json_path)
    return claude_json_path


def test_install_creates_settings_file(fake_settings, fake_claude_json):
    # install should create the settings file with hooks
    talktome.install()
    assert os.path.exists(fake_settings)
    with open(fake_settings) as f:
        settings = json.load(f)
    assert "hooks" in settings
    # mcp servers should not be in settings.json
    assert "mcpServers" not in settings


def test_install_creates_claude_json(fake_settings, fake_claude_json):
    # install should create .claude.json with mcp server
    talktome.install()
    assert os.path.exists(fake_claude_json)
    with open(fake_claude_json) as f:
        data = json.load(f)
    assert "mcpServers" in data


def test_install_adds_hooks(fake_settings, fake_claude_json):
    # install should add all five hook events
    talktome.install()
    with open(fake_settings) as f:
        settings = json.load(f)
    hooks = settings["hooks"]
    assert "SessionStart" in hooks
    assert "PreToolUse" in hooks
    assert "UserPromptSubmit" in hooks
    assert "Notification" in hooks
    assert "Stop" in hooks


def test_install_adds_mcp_server(fake_settings, fake_claude_json):
    # install should add the talktome mcp server to .claude.json
    talktome.install()
    with open(fake_claude_json) as f:
        data = json.load(f)
    assert "talktome" in data["mcpServers"]
    server = data["mcpServers"]["talktome"]
    assert server["type"] == "stdio"
    assert server["command"] == "talktome"
    assert server["args"] == ["proxy"]


def test_install_preserves_existing_settings(fake_settings, fake_claude_json):
    # install should not overwrite other settings
    existing = {"autoUpdatesChannel": "latest", "enabledPlugins": {"foo": True}}
    with open(fake_settings, "w") as f:
        json.dump(existing, f)

    talktome.install()
    with open(fake_settings) as f:
        settings = json.load(f)
    assert settings["autoUpdatesChannel"] == "latest"
    assert settings["enabledPlugins"]["foo"] is True
    assert "hooks" in settings


def test_install_preserves_existing_claude_json(fake_settings, fake_claude_json):
    # install should not overwrite other data in .claude.json
    existing = {"numStartups": 42, "projects": {"foo": {"bar": True}}}
    with open(fake_claude_json, "w") as f:
        json.dump(existing, f)

    talktome.install()
    with open(fake_claude_json) as f:
        data = json.load(f)
    assert data["numStartups"] == 42
    assert data["projects"]["foo"]["bar"] is True
    assert "mcpServers" in data


def test_install_preserves_existing_hooks(fake_settings, fake_claude_json):
    # install should not remove other hook entries
    existing = {
        "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "python other.py"}]}]}
    }
    with open(fake_settings, "w") as f:
        json.dump(existing, f)

    talktome.install()
    with open(fake_settings) as f:
        settings = json.load(f)

    # should have both the existing hook and the new talktome hook
    pretooluse = settings["hooks"]["PreToolUse"]
    commands = []
    for entry in pretooluse:
        for h in entry.get("hooks", []):
            commands.append(h.get("command", ""))
    assert any("other.py" in c for c in commands)
    assert any("talktome" in c for c in commands)


def test_install_cleans_stale_mcp_from_settings(fake_settings, fake_claude_json):
    # install should remove mcpServers from settings.json if present
    existing = {"mcpServers": {"talktome": {"command": "old"}}}
    with open(fake_settings, "w") as f:
        json.dump(existing, f)

    talktome.install()
    with open(fake_settings) as f:
        settings = json.load(f)
    assert "mcpServers" not in settings


def test_install_idempotent(fake_settings, fake_claude_json):
    # running install twice should not create duplicate entries
    talktome.install()
    talktome.install()
    with open(fake_settings) as f:
        settings = json.load(f)

    # each hook event should have exactly one talktome entry
    for event, entries in settings["hooks"].items():
        talktome_entries = [
            e
            for e in entries
            if any("talktome" in str(h.get("command", "")) for h in e.get("hooks", []))
        ]
        assert len(talktome_entries) == 1, f"duplicate talktome entries in {event}"

    # mcp server should appear exactly once in .claude.json
    with open(fake_claude_json) as f:
        data = json.load(f)
    assert "talktome" in data["mcpServers"]


def test_uninstall_removes_hooks(fake_settings, fake_claude_json):
    # uninstall should remove all talktome hook entries
    talktome.install()
    talktome.uninstall()
    with open(fake_settings) as f:
        settings = json.load(f)
    # hooks key should be gone since only talktome hooks existed
    assert "hooks" not in settings or not settings.get("hooks")


def test_uninstall_removes_mcp_server(fake_settings, fake_claude_json):
    # uninstall should remove the talktome mcp server from .claude.json
    talktome.install()
    talktome.uninstall()
    with open(fake_claude_json) as f:
        data = json.load(f)
    assert "talktome" not in data.get("mcpServers", {})


def test_uninstall_preserves_other_settings(fake_settings, fake_claude_json):
    # uninstall should not touch other settings
    existing = {"autoUpdatesChannel": "latest"}
    with open(fake_settings, "w") as f:
        json.dump(existing, f)
    talktome.install()
    talktome.uninstall()
    with open(fake_settings) as f:
        settings = json.load(f)
    assert settings["autoUpdatesChannel"] == "latest"


def test_uninstall_preserves_other_claude_json(fake_settings, fake_claude_json):
    # uninstall should not touch other data in .claude.json
    existing = {"numStartups": 42}
    with open(fake_claude_json, "w") as f:
        json.dump(existing, f)
    talktome.install()
    talktome.uninstall()
    with open(fake_claude_json) as f:
        data = json.load(f)
    assert data["numStartups"] == 42


def test_uninstall_preserves_other_hooks(fake_settings, fake_claude_json):
    # uninstall should not remove non talktome hook entries
    existing = {
        "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "python other.py"}]}]}
    }
    with open(fake_settings, "w") as f:
        json.dump(existing, f)

    talktome.install()
    talktome.uninstall()
    with open(fake_settings) as f:
        settings = json.load(f)

    # the other hook should still be there
    pretooluse = settings["hooks"]["PreToolUse"]
    commands = []
    for entry in pretooluse:
        for h in entry.get("hooks", []):
            commands.append(h.get("command", ""))
    assert any("other.py" in c for c in commands)
    assert not any("talktome" in c for c in commands)


def test_uninstall_when_not_installed(fake_settings, fake_claude_json):
    # uninstalling when not installed should not crash
    talktome.uninstall()
    with open(fake_settings) as f:
        settings = json.load(f)
    assert settings == {}


def test_hooks_use_talktome_binary(fake_settings, fake_claude_json):
    # all hook commands should use the talktome binary directly
    talktome.install()
    with open(fake_settings) as f:
        settings = json.load(f)
    for event, entries in settings["hooks"].items():
        for entry in entries:
            for h in entry.get("hooks", []):
                cmd = h.get("command", "")
                assert cmd.startswith("talktome hook-"), f"unexpected command in {event}: {cmd}"
