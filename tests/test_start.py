def _make_socket_factory(ports_that_fail: set[int]):
    bind_calls = []

    class DummySocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def bind(self, address):
            bind_calls.append(address)
            _, port = address
            if port in ports_that_fail:
                raise OSError("Port in use")

    def factory(*args, **kwargs):
        return DummySocket()

    return bind_calls, factory


def test_find_free_port_checks_only_loopback(monkeypatch):
    import start

    bind_calls, socket_factory = _make_socket_factory(set())
    monkeypatch.setattr("start.socket.socket", socket_factory)

    port = start.find_free_port(8050, 8051)

    assert port == 8050
    assert bind_calls == [("127.0.0.1", 8050)]


def test_find_free_port_falls_back_when_first_port_is_unavailable(monkeypatch):
    import start

    bind_calls, socket_factory = _make_socket_factory({8050})
    monkeypatch.setattr("start.socket.socket", socket_factory)

    port = start.find_free_port(8050, 8052)

    assert port == 8051
    assert bind_calls == [("127.0.0.1", 8050), ("127.0.0.1", 8051)]


def test_find_free_port_returns_none_when_range_is_exhausted(monkeypatch):
    import start

    bind_calls, socket_factory = _make_socket_factory({8050, 8051})
    monkeypatch.setattr("start.socket.socket", socket_factory)

    port = start.find_free_port(8050, 8052)

    assert port is None
    assert bind_calls == [("127.0.0.1", 8050), ("127.0.0.1", 8051)]


def test_ensure_supported_python_version_accepts_supported_tuple():
    import start

    assert start.ensure_supported_python_version((3, 10, 0)) is True
    assert start.ensure_supported_python_version((3, 12, 1)) is True


def test_ensure_supported_python_version_rejects_older_versions(capsys):
    import start

    assert start.ensure_supported_python_version((3, 9, 18)) is False
    captured = capsys.readouterr()
    assert "Python 3.10+ e obrigatorio" in captured.out
