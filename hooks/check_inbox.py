import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request

# lightweight mailbox check for pretooluse, userpromptsubmit, notification hooks
# peeks at mailbox and injects additional context if messages are waiting
BRIDGE_URL = os.environ.get("TALKTOME_URL", "http://127.0.0.1:3456")
COOLDOWN_SECONDS = 10


def main():
    hook_input = json.loads(sys.stdin.read())

    # read identity file to know who we are
    # file is json with name and session_id, or plain text for old format
    identity_file = os.path.join(hook_input["cwd"], ".claude", ".bridge-identity")
    if not os.path.exists(identity_file):
        sys.exit(0)

    with open(identity_file) as f:
        raw = f.read().strip()

    try:
        identity = json.loads(raw)
        name = identity.get("name", "")
    except (ValueError, json.JSONDecodeError):
        name = raw

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


if __name__ == "__main__":
    main()
