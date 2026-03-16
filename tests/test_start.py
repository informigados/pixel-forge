def test_find_free_port_checks_only_loopback(monkeypatch):
    import start

    bind_calls = []

    class DummySocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def bind(self, address):
            bind_calls.append(address)

    monkeypatch.setattr("start.socket.socket", lambda *args, **kwargs: DummySocket())

    port = start.find_free_port(8050, 8051)

    assert port == 8050
    assert bind_calls == [("127.0.0.1", 8050)]
