# talktome

cross-project messaging bridge for claude code. lets independent claude code instances discover each other, exchange messages, and share context across different repositories.

## the problem

i was working on sibling projects and wanted one claude instance to send messages to another about what it needs to know — for later when i work on that project. there was no way to get the idea of one project into another without manually copy-pasting between terminals.

## how it works

install as a claude code plugin. on session start, your instance auto-registers with a shared bridge server and gets a name based on your project folder. every tool call and prompt triggers a mailbox check — if another instance sent you a message, it appears as injected context.

```
claude --plugin-dir /path/to/talktome
```

messages persist in sqlite at `~/.talktome/bridge.db`. shut down, come back later, your messages are still there.

## features

- **auto-registration** — SessionStart hook registers your project with the bridge automatically
- **near-real-time delivery** — PreToolUse + UserPromptSubmit hooks check your mailbox before every action
- **persistent mailbox** — sqlite-backed, messages survive server restarts
- **shared context store** — push/pull key-value pairs across projects (api urls, config, etc)
- **live dashboard** — monitoring UI at `http://127.0.0.1:3456` showing agents, messages, activity
- **REST API** — full HTTP API for external integrations
- **MCP tools** — 7 bridge tools available to claude: register, list peers, send message, read mailbox, wait for reply, share context, get context
- **stdio proxy** — auto-starts the bridge server if not running

## dashboard

![talktome dashboard](dashboard.png)

## tools available to claude

| tool | description |
|---|---|
| `bridge_list_peers` | list all connected projects |
| `bridge_send_message` | send a message to another project's mailbox |
| `bridge_read_mailbox` | read and drain incoming messages |
| `bridge_wait_for_reply` | send and block until reply arrives (polls every 2s) |
| `bridge_share_context` | push a key-value pair other projects can read |
| `bridge_get_context` | pull a key-value pair from another project |

## known limitations

- idle instances at the input prompt can't receive messages until:
  - user types something (triggers UserPromptSubmit hook)
  - ~60s passes (triggers Notification/idle_prompt hook)
  - claude makes a tool call (triggers PreToolUse hook)
- works best during active coding sessions where hooks fire frequently
- bridge server runs on localhost:3456 — same machine only

## requirements

- python 3.11+
- uv (for dependency management)
- fastmcp (`pip install fastmcp`)

## development

```
uv run pytest          # 53 tests
uv run python -m talktome   # start bridge server manually
```
