import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

PORT = 3456
URL = f"http://127.0.0.1:{PORT}"

# path to the claude code global settings file (hooks live here)
CLAUDE_SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")

# path to the claude code user config file (mcp servers live here)
CLAUDE_JSON_PATH = os.path.join(os.path.expanduser("~"), ".claude.json")


# check if the bridge server is already responding on the port
def is_running():
    try:
        req = urllib.request.Request(f"{URL}/health")
        resp = urllib.request.urlopen(req, timeout=3)
        return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


# poll until the server is up then open the browser
def wait_and_open():
    for i in range(20):
        time.sleep(0.3)
        if is_running():
            webbrowser.open(URL)
            return
    # server never came up but try anyway
    webbrowser.open(URL)


# read the claude settings file, return empty dict if missing
def read_settings():
    if not os.path.exists(CLAUDE_SETTINGS_PATH):
        return {}
    try:
        with open(CLAUDE_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


# write the settings dict back to the claude settings file
def write_settings(settings):
    os.makedirs(os.path.dirname(CLAUDE_SETTINGS_PATH), exist_ok=True)
    with open(CLAUDE_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


# build the hook entries using the global talktome binary
def build_hooks():
    return {
        "SessionStart": [
            {
                "matcher": "startup|resume",
                "hooks": [{"type": "command", "command": "talktome hook-register", "timeout": 15}],
            }
        ],
        "PreToolUse": [
            {
                "hooks": [{"type": "command", "command": "talktome hook-inbox", "timeout": 5}],
            }
        ],
        "UserPromptSubmit": [
            {
                "hooks": [{"type": "command", "command": "talktome hook-inbox", "timeout": 5}],
            }
        ],
        "Notification": [
            {
                "matcher": "idle_prompt",
                "hooks": [{"type": "command", "command": "talktome hook-inbox", "timeout": 5}],
            }
        ],
        "Stop": [
            {
                "hooks": [{"type": "command", "command": "talktome hook-mailbox", "timeout": 10}],
            }
        ],
    }


# read the claude user config file, return empty dict if missing
def read_claude_json():
    if not os.path.exists(CLAUDE_JSON_PATH):
        return {}
    try:
        with open(CLAUDE_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


# write the claude user config file back
def write_claude_json(data):
    with open(CLAUDE_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# build the mcp server entry using the global talktome binary
def build_mcp_server():
    return {
        "type": "stdio",
        "command": "talktome",
        "args": ["proxy"],
    }


# add talktome hooks and mcp server to claude global settings
def install():
    # hooks go to ~/.claude/settings.json
    settings = read_settings()

    # merge hooks into existing hooks, preserving other hook entries
    existing_hooks = settings.get("hooks", {})
    talktome_hooks = build_hooks()
    for event, entries in talktome_hooks.items():
        if event not in existing_hooks:
            existing_hooks[event] = []
        # remove any existing talktome entries for this event to avoid duplicates
        existing_hooks[event] = [
            e
            for e in existing_hooks[event]
            if not any("talktome" in str(h.get("command", "")) for h in e.get("hooks", []))
        ]
        # add the new talktome entries
        existing_hooks[event].extend(entries)
    settings["hooks"] = existing_hooks

    # clean up stale mcpServers from settings.json (they belong in .claude.json)
    if "mcpServers" in settings:
        del settings["mcpServers"]

    write_settings(settings)

    # mcp server goes to ~/.claude.json (user scope, available in all projects)
    claude_json = read_claude_json()
    mcp_servers = claude_json.get("mcpServers", {})
    mcp_servers["talktome"] = build_mcp_server()
    claude_json["mcpServers"] = mcp_servers
    write_claude_json(claude_json)

    print("talktome installed globally")
    print(f"  hooks added to {CLAUDE_SETTINGS_PATH}")
    print(f"  mcp server added to {CLAUDE_JSON_PATH}")
    print("  every new claude code session will now auto register")
    print("  run 'talktome' to start the dashboard")


# remove talktome hooks and mcp server from claude global settings
def uninstall():
    # remove hooks from ~/.claude/settings.json
    settings = read_settings()

    existing_hooks = settings.get("hooks", {})
    for event in list(existing_hooks.keys()):
        existing_hooks[event] = [
            e
            for e in existing_hooks[event]
            if not any("talktome" in str(h.get("command", "")) for h in e.get("hooks", []))
        ]
        # remove the event key entirely if no entries remain
        if not existing_hooks[event]:
            del existing_hooks[event]
    if existing_hooks:
        settings["hooks"] = existing_hooks
    elif "hooks" in settings:
        del settings["hooks"]

    # also clean up stale mcpServers from settings.json if present
    if "mcpServers" in settings:
        del settings["mcpServers"]

    write_settings(settings)

    # remove mcp server from ~/.claude.json
    claude_json = read_claude_json()
    mcp_servers = claude_json.get("mcpServers", {})
    if "talktome" in mcp_servers:
        del mcp_servers["talktome"]
    if mcp_servers:
        claude_json["mcpServers"] = mcp_servers
    elif "mcpServers" in claude_json:
        del claude_json["mcpServers"]
    write_claude_json(claude_json)

    print("talktome uninstalled")
    print(f"  hooks removed from {CLAUDE_SETTINGS_PATH}")
    print(f"  mcp server removed from {CLAUDE_JSON_PATH}")


# start the bridge server and open the dashboard
def start(open_browser=True):
    # if bridge already running just open browser and exit
    if is_running():
        print(f"talktome already running at {URL}")
        if open_browser:
            webbrowser.open(URL)
        return

    print(f"starting talktome on {URL}...")

    # open browser in a background thread once server is ready
    if open_browser:
        opener = threading.Thread(target=wait_and_open, daemon=True)
        opener.start()

    # run the server in the foreground, blocks until interrupted
    from talktome.server import mcp

    try:
        mcp.run(transport="http", host="0.0.0.0", port=PORT)
    except KeyboardInterrupt:
        print("\ntalktome stopped")
        sys.exit(0)


# run the stdio mcp proxy, auto starting the bridge if needed
def run_proxy():
    from talktome.hooks import ensure_bridge
    from talktome.proxy import proxy

    ensure_bridge()
    proxy.run()


# cli entry point, routes to subcommands or starts the dashboard
def main():
    command = sys.argv[1].lower() if len(sys.argv) > 1 else ""

    if command == "install":
        install()
    elif command == "uninstall":
        uninstall()
    elif command == "proxy":
        run_proxy()
    elif command == "hook-register":
        from talktome.hooks import hook_register

        hook_register()
    elif command == "hook-inbox":
        from talktome.hooks import hook_inbox

        hook_inbox()
    elif command == "hook-mailbox":
        from talktome.hooks import hook_mailbox

        hook_mailbox()
    elif command == "--no-browser":
        start(open_browser=False)
    else:
        start()
