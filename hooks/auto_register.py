import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

# auto starts bridge server and registers this codebase
BRIDGE_URL = os.environ.get("TALKTOME_URL", "http://127.0.0.1:3456")
TALKTOME_DIR = os.environ.get(
    "TALKTOME_DIR",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)


def is_bridge_running():
    try:
        req = urllib.request.Request(f"{BRIDGE_URL}/health")
        resp = urllib.request.urlopen(req, timeout=3)
        return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def start_bridge():
    # start the bridge server in the background
    if sys.platform == "win32":
        subprocess.Popen(
            ["uv", "run", "--no-sync", "--directory", TALKTOME_DIR, "python", "-m", "talktome"],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.Popen(
            ["uv", "run", "--no-sync", "--directory", TALKTOME_DIR, "python", "-m", "talktome"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # wait for server to come up
    for _ in range(10):
        time.sleep(0.5)
        if is_bridge_running():
            return True
    return False


# parent folder names that are too generic to use as a prefix
GENERIC_PARENTS = {
    "desktop",
    "projects",
    "repos",
    "code",
    "src",
    "home",
    "users",
    "documents",
    "downloads",
    "coding",
    "work",
    "dev",
    "github",
    "gitlab",
    "bitbucket",
    "coding-projects",
    "my-projects",
    "personal-projects",
}


# derive an agent name from the project path
# uses parent folder as prefix to avoid collisions between projects
# with the same folder name, skips generic parent names
def derive_agent_name(cwd):
    normalized = cwd.replace("\\", "/").rstrip("/")
    parts = normalized.split("/")
    folder = parts[-1] if parts else "unknown"
    parent = parts[-2] if len(parts) >= 2 else ""

    # clean up the folder and parent names
    folder = folder.lower().replace(" ", "-")
    parent = parent.lower().replace(" ", "-")

    # skip generic parent names, just use the folder
    if not parent or parent in GENERIC_PARENTS:
        return folder

    return f"{parent}-{folder}"


def main():
    hook_input = json.loads(sys.stdin.read())
    cwd = hook_input["cwd"]
    session_id = hook_input.get("session_id", "")

    # derive agent name from the project path with parent prefix
    name = derive_agent_name(cwd)

    # ensure bridge is running
    if not is_bridge_running():
        if not start_bridge():
            sys.exit(0)

    # store identity so the stop hook knows who we are
    claude_dir = os.path.join(cwd, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    identity_file = os.path.join(claude_dir, ".bridge-identity")
    with open(identity_file, "w") as f:
        json.dump({"name": name, "session_id": session_id}, f)

    # register directly via rest
    payload = json.dumps({"name": name, "path": cwd, "session_id": session_id}).encode()
    try:
        req = urllib.request.Request(
            f"{BRIDGE_URL}/register",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except (urllib.error.URLError, OSError):
        pass

    result = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                f"you are registered with the talktome bridge as '{name}'. "
                f"bridge tools: bridge_list_peers, bridge_send_message, "
                f"bridge_read_mailbox, bridge_wait_for_reply, "
                f"bridge_share_context, bridge_get_context. "
                f"your mailbox is checked automatically before every action "
                f"and when you receive a prompt. incoming messages appear as "
                f"context — read them with bridge_read_mailbox('{name}') and "
                f"respond via bridge_send_message. use bridge_wait_for_reply "
                f"to send a message and wait for a response in one turn."
            ),
        }
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
