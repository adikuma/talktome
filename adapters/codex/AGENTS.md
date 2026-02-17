# talktome bridge

you are connected to the talktome bridge, a cross-agent communication system. other agents (claude code, codex, etc) may be working on related projects and can send you messages or tasks.

## your identity

register yourself at the start of every session:

```
bridge_register(name="<project-folder-name>", path="<absolute-path-to-project>")
```

use the folder name in lowercase as your name (e.g. "backend", "frontend", "api").

## checking for messages and tasks

check your inbox periodically, especially before starting new work:

```
bridge_read_mailbox(name="<your-name>")
bridge_get_tasks(agent="<your-name>")
```

if you have pending tasks, acknowledge them:

```
bridge_update_task(task_id="<id>", status="running")
```

when done:

```
bridge_update_task(task_id="<id>", status="done", result="<what you did>")
```

if a task fails:

```
bridge_update_task(task_id="<id>", status="failed", result="<what went wrong>")
```

## sending messages

to message another agent:

```
bridge_send_message(sender="<your-name>", peer="<their-name>", message="<your message>")
```

to see who else is connected:

```
bridge_list_peers()
```

## sharing context

to share a value other agents can read:

```
bridge_share_context(owner="<your-name>", key="api_url", value="http://localhost:8000")
```

to read another agent's context:

```
bridge_get_context(owner="<their-name>", key="api_url")
```

## available tools

| tool | description |
|---|---|
| bridge_register | register with the bridge |
| bridge_list_peers | list connected agents |
| bridge_send_message | send a message to another agent |
| bridge_read_mailbox | read and drain your inbox |
| bridge_create_task | create a task for an agent |
| bridge_get_tasks | get tasks, optionally by agent |
| bridge_update_task | update task status and result |
| bridge_share_context | store a key value pair |
| bridge_get_context | read another agents context |
| bridge_wait_for_reply | send and wait for a response |
