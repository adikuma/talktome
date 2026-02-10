import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request

# lightweight mailbox check for PreToolUse, UserPromptSubmit, Notification hooks
# peeks at mailbox and injects additionalContext if messages are waiting
BRIDGE_URL = os.environ.get("TALKTOME_URL", "http://127.0.0.1:3456")
COOLDOWN_SECONDS = 10


def main():
    hook_input = json.loads(sys.stdin.read())

    # read identity file to know who we are
    identity_file = os.path.join(hook_input["cwd"], ".claude", ".bridge-identity")
    if not os.path.exists(identity_file):
        sys.exit(0)

    with open(identity_file) as f:
        name = f.read().strip()

    if not name:
        sys.exit(0)

    # cooldown — skip if we checked recently
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

    # peek at mailbox
    try:
        req = urllib.request.Request(f"{BRIDGE_URL}/peek/{name}")
        resp = urllib.request.urlopen(req, timeout=3)
        data = json.loads(resp.read())
    except (urllib.error.URLError, OSError):
        sys.exit(0)

    if data["count"] == 0:
        sys.exit(0)

    # messages waiting — inject as additional context
    messages = data["messages"]
    preview = "; ".join(f"[{m['from']}]: {m['message'][:120]}" for m in messages[:5])
    result = {
        "additionalContext": (
            f"[talktome] {data['count']} new message(s) in your mailbox. "
            f"preview: {preview}. "
            f"call bridge_read_mailbox('{name}') to read and respond."
        ),
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
