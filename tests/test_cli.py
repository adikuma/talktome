import unittest.mock as mock


from talktome import is_running, wait_and_open


def test_is_running_returns_false_when_no_server(monkeypatch):
    # with no server running, is running should return false
    import urllib.error

    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("talktome.urllib.request.urlopen", fake_urlopen)
    assert is_running() is False


def test_is_running_returns_true_on_200(monkeypatch):
    # mock a successful health check response
    fake_resp = mock.MagicMock()
    fake_resp.status = 200

    def fake_urlopen(req, timeout=None):
        return fake_resp

    monkeypatch.setattr("talktome.urllib.request.urlopen", fake_urlopen)
    assert is_running() is True


def test_is_running_returns_false_on_error(monkeypatch):
    # mock a connection error from urlopen
    import urllib.error

    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("talktome.urllib.request.urlopen", fake_urlopen)
    assert is_running() is False


def test_wait_and_open_opens_browser_when_ready(monkeypatch):
    # simulate server becoming ready on the second check
    call_count = {"n": 0}

    def fake_is_running():
        call_count["n"] += 1
        return call_count["n"] >= 2

    opened = {"url": None}

    def fake_open(url):
        opened["url"] = url

    monkeypatch.setattr("talktome.is_running", fake_is_running)
    monkeypatch.setattr("talktome.webbrowser.open", fake_open)
    monkeypatch.setattr("talktome.time.sleep", lambda x: None)

    wait_and_open()
    assert opened["url"] is not None
    assert "127.0.0.1" in opened["url"]


def test_wait_and_open_opens_browser_even_on_timeout(monkeypatch):
    # if the server never comes up, browser should open anyway
    def fake_is_running():
        return False

    opened = {"url": None}

    def fake_open(url):
        opened["url"] = url

    monkeypatch.setattr("talktome.is_running", fake_is_running)
    monkeypatch.setattr("talktome.webbrowser.open", fake_open)
    monkeypatch.setattr("talktome.time.sleep", lambda x: None)

    wait_and_open()
    assert opened["url"] is not None


def test_main_opens_browser_if_already_running(monkeypatch):
    # if server is already running, main should just open browser and return
    monkeypatch.setattr("sys.argv", ["talktome"])
    monkeypatch.setattr("talktome.is_running", lambda: True)

    opened = {"count": 0}

    def fake_open(url):
        opened["count"] += 1

    monkeypatch.setattr("talktome.webbrowser.open", fake_open)

    from talktome import main

    main()
    assert opened["count"] == 1


def test_main_starts_server_if_not_running(monkeypatch):
    # if server is not running, main should start it
    monkeypatch.setattr("sys.argv", ["talktome"])
    monkeypatch.setattr("talktome.is_running", lambda: False)

    started = {"called": False}

    class FakeMcp:
        def run(self, **kwargs):
            started["called"] = True

    monkeypatch.setattr("talktome.server.mcp", FakeMcp())
    monkeypatch.setattr("talktome.webbrowser.open", lambda url: None)
    monkeypatch.setattr("talktome.time.sleep", lambda x: None)

    # mock threading to avoid actual background thread
    import threading

    original_thread = threading.Thread

    def fake_thread(*args, **kwargs):
        t = original_thread(*args, **kwargs)
        # don't actually start it, just record that it was created
        t.start = lambda: None
        return t

    monkeypatch.setattr("talktome.threading.Thread", fake_thread)

    from talktome import main

    main()
    assert started["called"] is True


def test_main_routes_to_install(monkeypatch):
    # talktome install should call the install function
    monkeypatch.setattr("sys.argv", ["talktome", "install"])

    called = {"install": False}

    def fake_install():
        called["install"] = True

    monkeypatch.setattr("talktome.install", fake_install)

    from talktome import main

    main()
    assert called["install"] is True


def test_main_routes_to_proxy(monkeypatch):
    # talktome proxy should call run_proxy
    monkeypatch.setattr("sys.argv", ["talktome", "proxy"])

    called = {"proxy": False}

    def fake_run_proxy():
        called["proxy"] = True

    monkeypatch.setattr("talktome.run_proxy", fake_run_proxy)

    from talktome import main

    main()
    assert called["proxy"] is True


def test_main_routes_to_hook_register(monkeypatch):
    # talktome hook-register should call the hook function
    monkeypatch.setattr("sys.argv", ["talktome", "hook-register"])

    called = {"hook": False}

    def fake_hook():
        called["hook"] = True

    monkeypatch.setattr("talktome.hooks.hook_register", fake_hook)

    from talktome import main

    main()
    assert called["hook"] is True


def test_main_routes_to_hook_inbox(monkeypatch):
    # talktome hook-inbox should call the hook function
    monkeypatch.setattr("sys.argv", ["talktome", "hook-inbox"])

    called = {"hook": False}

    def fake_hook():
        called["hook"] = True

    monkeypatch.setattr("talktome.hooks.hook_inbox", fake_hook)

    from talktome import main

    main()
    assert called["hook"] is True


def test_main_routes_to_hook_mailbox(monkeypatch):
    # talktome hook-mailbox should call the hook function
    monkeypatch.setattr("sys.argv", ["talktome", "hook-mailbox"])

    called = {"hook": False}

    def fake_hook():
        called["hook"] = True

    monkeypatch.setattr("talktome.hooks.hook_mailbox", fake_hook)

    from talktome import main

    main()
    assert called["hook"] is True
