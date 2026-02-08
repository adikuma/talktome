from talktome import queue


def setup_function():
    queue.mailboxes.clear()


def test_send_creates_mailbox():
    entry = queue.send("backend", "frontend", "hello")
    assert entry["from"] == "backend"
    assert entry["message"] == "hello"
    assert "timestamp" in entry
    assert queue.count("frontend") == 1


def test_send_multiple_messages():
    queue.send("backend", "frontend", "first")
    queue.send("backend", "frontend", "second")
    assert queue.count("frontend") == 2


def test_send_from_different_senders():
    queue.send("backend", "frontend", "from backend")
    queue.send("api", "frontend", "from api")
    assert queue.count("frontend") == 2


def test_read_returns_messages():
    queue.send("backend", "frontend", "hey")
    messages = queue.read("frontend")
    assert len(messages) == 1
    assert messages[0]["from"] == "backend"
    assert messages[0]["message"] == "hey"


def test_read_drains_mailbox():
    queue.send("backend", "frontend", "hey")
    queue.read("frontend")
    assert queue.count("frontend") == 0
    assert queue.read("frontend") == []


def test_read_empty_mailbox():
    assert queue.read("nobody") == []


def test_peek_returns_without_clearing():
    queue.send("backend", "frontend", "hey")
    messages = queue.peek("frontend")
    assert len(messages) == 1
    assert queue.count("frontend") == 1


def test_peek_empty_mailbox():
    assert queue.peek("nobody") == []


def test_clear_empties_mailbox():
    queue.send("backend", "frontend", "hey")
    assert queue.clear("frontend") is True
    assert queue.count("frontend") == 0


def test_clear_nonexistent_returns_false():
    assert queue.clear("nobody") is False


def test_count_empty():
    assert queue.count("nobody") == 0


def test_count_after_send():
    queue.send("backend", "frontend", "one")
    queue.send("backend", "frontend", "two")
    queue.send("backend", "frontend", "three")
    assert queue.count("frontend") == 3
