import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

BRIDGE_URL = os.environ.get("TALKTOME_URL", "http://127.0.0.1:3456")
COOLDOWN_SECONDS = 10

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


def is_bridge_running():
    try:
        req = urllib.request.Request(f"{BRIDGE_URL}/health")
        resp = urllib.request.urlopen(req, timeout=3)
        return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def start_bridge():
    # start the bridge server in the background using the global binary
    if sys.platform == "win32":
        subprocess.Popen(
            ["talktome"],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.Popen(
            ["talktome"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # wait for server to come up
    for _ in range(15):
        time.sleep(0.5)
        if is_bridge_running():
            return True
    return False


def ensure_bridge():
    if not is_bridge_running():
        return start_bridge()
    return True


# read the identity file from a project directory
# returns the agent name or empty string if not found
def read_identity(cwd):
    identity_file = os.path.join(cwd, ".claude", ".bridge-identity")
    if not os.path.exists(identity_file):
        return ""
    try:
        with open(identity_file) as f:
            raw = f.read().strip()
        try:
            identity = json.loads(raw)
            return identity.get("name", "")
        except (ValueError, json.JSONDecodeError):
            return raw
    except OSError:
        return ""


def hook_register():
    hook_input = json.loads(sys.stdin.read())
    cwd = hook_input["cwd"]
    session_id = hook_input.get("session_id", "")

    # derive agent name from the project path with parent prefix
    name = derive_agent_name(cwd)

    # ensure bridge is running
    if not is_bridge_running():
        if not start_bridge():
            sys.exit(0)

    # store identity so the other hooks know who we are
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


def hook_inbox():
    hook_input = json.loads(sys.stdin.read())

    name = read_identity(hook_input["cwd"])
    if not name:
        sys.exit(0)

    # cooldown, skip if we checked recently
    cooldown_file = os.path.join(tempfile.gettempdir(), f"talktome-inbox-{name}")
    now = time.time()
    if os.path.exists(cooldown_file):
        try:
            with open(cooldown_file) as f:
                last_check = float(f.read().strip())
            if now - last_check < COOLDOWN_SECONDS:
                sys.exit(0)
        except (ValueError, OSError):
            pass

    # update cooldown timestamp
    try:
        with open(cooldown_file, "w") as f:
            f.write(str(now))
    except OSError:
        pass

    # peek at mailbox + pending tasks
    parts = []

    try:
        req = urllib.request.Request(f"{BRIDGE_URL}/peek/{name}")
        resp = urllib.request.urlopen(req, timeout=3)
        data = json.loads(resp.read())
        if data["count"] > 0:
            messages = data["messages"]
            preview = "; ".join(f"[{m['from']}]: {m['message'][:120]}" for m in messages[:5])
            parts.append(
                f"{data['count']} new message(s). "
                f"preview: {preview}. "
                f"call bridge_read_mailbox('{name}') to read and respond."
            )
    except (urllib.error.URLError, OSError):
        pass

    try:
        req = urllib.request.Request(f"{BRIDGE_URL}/tasks/{name}/pending")
        resp = urllib.request.urlopen(req, timeout=3)
        tasks = json.loads(resp.read())
        if tasks:
            task_preview = "; ".join(f"[{t['id']}]: {t['description'][:120]}" for t in tasks[:5])
            parts.append(
                f"{len(tasks)} pending task(s). "
                f"preview: {task_preview}. "
                f"call bridge_get_tasks('{name}') to see details, "
                f"bridge_update_task(task_id, 'running') to start."
            )
    except (urllib.error.URLError, OSError):
        pass

    if not parts:
        sys.exit(0)

    result = {
        "additionalContext": "[talktome] " + " | ".join(parts),
    }
    print(json.dumps(result))
    sys.exit(0)


def hook_mailbox():
    hook_input = json.loads(sys.stdin.read())

    # prevent infinite loops, if we already blocked once then let claude stop
    if hook_input.get("stop_hook_active"):
        sys.exit(0)

    name = read_identity(hook_input["cwd"])
    if not name:
        sys.exit(0)

    # check for pending messages
    try:
        req = urllib.request.Request(f"{BRIDGE_URL}/peek/{name}")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
    except (urllib.error.URLError, OSError):
        # bridge not running so let claude stop
        sys.exit(0)

    if data["count"] == 0:
        sys.exit(0)

    # messages waiting, block claude from stopping
    messages = data["messages"]
    preview = "; ".join(f"[{m['from']}]: {m['message'][:80]}" for m in messages[:5])
    result = {
        "decision": "block",
        "reason": (
            f"you have {data['count']} pending message(s) in your mailbox. "
            f"call bridge_read_mailbox('{name}') to read them. "
            f"preview: {preview}"
        ),
    }
    print(json.dumps(result))
    sys.exit(0)
