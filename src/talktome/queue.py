from talktome import db

# thin wrapper — delegates to sqlite-backed db module


def send(sender_agent, receiver_agent, message):
    return db.send_message(sender_agent, receiver_agent, message)


def read(agent):
    return db.read_messages(agent)


def peek(agent):
    return db.peek_messages(agent)


def clear(agent):
    return db.clear_messages(agent)


def count(agent):
    return db.message_count(agent)
