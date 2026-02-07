import time

mailboxes: dict[str, list[dict]] = {}


# when a message is sent we add it to the mailbox of the receiver
def send(sender_agent: str, receiver_agent: str, message: str) -> dict:
    entry = {"from": sender_agent, "message": message, "timestamp": time.time()}
    if receiver_agent not in mailboxes:
        mailboxes[receiver_agent] = []
    mailboxes[receiver_agent].append(entry)
    return entry


# read the messages for an agent
def read(agent: str) -> list[dict]:
    if agent not in mailboxes:
        return []
    messages = mailboxes[agent]
    # the idea is to drain the mailbox once the agent has read them
    mailboxes[agent] = []
    return messages


# read the messages without clearing them
def peek(agent: str) -> list[dict]:
    if agent not in mailboxes:
        return []
    return mailboxes[agent]


# clear the mailbox of the agent
def clear(agent: str) -> bool:
    if agent not in mailboxes:
        return False
    mailboxes[agent] = []
    return True


# count
def count(agent: str) -> int:
    if agent not in mailboxes:
        return 0
    return len(mailboxes[agent])
