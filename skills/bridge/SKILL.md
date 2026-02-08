---
name: bridge
description: communicate with other claude code instances via the talktome bridge.
  use when the user asks about other projects, wants to send messages to other
  codebases, or needs cross-project coordination.
---
you have access to bridge tools for cross-project communication:
- bridge_register: register this codebase with the bridge
- bridge_list_peers: see who's connected
- bridge_send_message: send a message to another codebase
- bridge_read_mailbox: check for incoming messages
- bridge_share_context: push context for others to read
- bridge_get_context: pull context from others

always check your mailbox when starting cross-project work.
when you finish a task, your mailbox is checked automatically via a hook.
if you receive messages, read and respond to them before stopping.
