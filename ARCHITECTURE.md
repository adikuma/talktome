# Architecture

## Overview

A bridge server that lets multiple Claude Code instances discover each other, exchange messages, and share context. Runs as an MCP server over HTTP with SQLite persistence.

## System diagram

```mermaid
graph TB
    subgraph "Claude Code Instance A"
        A_Hooks[Hooks<br/>SessionStart / PreToolUse / UserPromptSubmit]
        A_Proxy[stdio proxy]
    end

    subgraph "Claude Code Instance B"
        B_Hooks[Hooks<br/>SessionStart / PreToolUse / UserPromptSubmit]
        B_Proxy[stdio proxy]
    end

    subgraph "Bridge Server :3456"
        Server[server.py<br/>MCP tools + REST API]
        Registry[registry.py<br/>agent phonebook]
        Queue[queue.py<br/>message mailboxes]
        DB[(SQLite<br/>~/.talktome/bridge.db)]
        Dashboard[dashboard.html<br/>monitoring UI]
    end

    A_Proxy -->|HTTP| Server
    B_Proxy -->|HTTP| Server
    A_Hooks -->|auto-register<br/>check inbox| Server
    B_Hooks -->|auto-register<br/>check inbox| Server
    Server --> Registry
    Server --> Queue
    Registry --> DB
    Queue --> DB
    Server --> Dashboard
```

## Data flow

```mermaid
sequenceDiagram
    participant A as Instance A (frontend)
    participant S as Bridge Server
    participant B as Instance B (api)

    A->>S: SessionStart → bridge_register("frontend", "/path")
    B->>S: SessionStart → bridge_register("api", "/path")
    A->>S: bridge_list_peers()
    S-->>A: ["api"]
    A->>S: bridge_send_message("api", "what auth endpoint?")
    Note over S: Message stored in SQLite
    B->>S: PreToolUse → check_inbox
    S-->>B: Injects message as context
    B->>S: bridge_share_context("auth_endpoint", "/api/login")
    A->>S: bridge_get_context("api", "auth_endpoint")
    S-->>A: "/api/login"
```

## Files

| File | Purpose |
|---|---|
| `src/talktome/server.py` | MCP tools + REST endpoints + dashboard |
| `src/talktome/db.py` | SQLite persistence layer (WAL mode) |
| `src/talktome/registry.py` | Agent registration, thin wrapper over db |
| `src/talktome/queue.py` | Message mailboxes, thin wrapper over db |
| `src/talktome/proxy.py` | Stdio-to-HTTP proxy, auto-starts bridge |
| `src/talktome/dashboard.html` | Live monitoring UI |
| `hooks/hooks.json` | Hook definitions for all lifecycle events |
| `hooks/auto_register.py` | SessionStart hook, registers agent with bridge |
| `hooks/check_inbox.py` | PreToolUse/UserPromptSubmit hook, polls mailbox |
| `skills/bridge/SKILL.md` | Slash command instructions for Claude |

## Database schema

```mermaid
erDiagram
    agents {
        text name PK
        text path
        text status
        real registered_at
        real last_seen
        text metadata
    }

    messages {
        int id PK
        text sender
        text receiver
        text message
        real timestamp
        int read
    }

    context {
        text owner PK
        text key PK
        text value
    }

    activity {
        int id PK
        text event
        real timestamp
        text data
    }
```
