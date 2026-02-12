---
name: bridge
description: Communicate with other Claude Code instances via the talktome bridge.
  Use when the user asks about other projects, wants to send messages to other
  codebases, or needs cross-project coordination.
---
You have access to bridge tools for cross-project communication:
- bridge_register: Register this codebase with the bridge
- bridge_list_peers: See who's connected
- bridge_send_message: Send a message to another codebase
- bridge_read_mailbox: Check for incoming messages
- bridge_share_context: Push context for others to read
- bridge_get_context: Pull context from others

Always check your mailbox when starting cross-project work.
When you finish a task, your mailbox is checked automatically via a hook.
If you receive messages, read and respond to them before stopping.
