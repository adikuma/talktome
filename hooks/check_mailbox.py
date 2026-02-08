import json
import os
import sys
import urllib.error
import urllib.request

BRIDGE_URL = os.environ.get("TALKTOME_URL", "http://localhost:3456")


def main():
    hook_input = json.loads(sys.stdin.read())

    # prevent infinite loops // if we already blocked once then let claude stop
    if hook_input.get("stop_hook_active"):
        sys.exit(0)

    # read identity file to know who we are
    identity_file = os.path.join(hook_input["cwd"], ".claude", ".bridge-identity")
    if not os.path.exists(identity_file):
        sys.exit(0)

    with open(identity_file) as f:
        name = f.read().strip()

    if not name:
        sys.exit(0)

    # check for pending messages
    try:
        req = urllib.request.Request(f"{BRIDGE_URL}/peek/{name}")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
    except (urllib.error.URLError, OSError):
        # bridge not running, let claude stop
        sys.exit(0)

    if data["count"] == 0:
        sys.exit(0)

    # messages waiting which is to block claude from stopping
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


if __name__ == "__main__":
    main()
