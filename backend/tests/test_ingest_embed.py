import httpx
from ingest.__main__ import main


def test_embed_without_live_makes_no_request(monkeypatch, capsys) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("client was built")

    monkeypatch.setattr("ingest.__main__.create_engine", boom)
    monkeypatch.setattr(httpx, "Client", boom)
    monkeypatch.setattr(httpx, "post", boom)
    assert main(["embed"]) == 2
    assert "No request was sent" in capsys.readouterr().err


def test_embed_live_without_a_key_makes_no_request(monkeypatch, capsys) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("client was built")

    monkeypatch.setattr("ingest.__main__.create_engine", boom)
    monkeypatch.setattr(httpx, "Client", boom)
    monkeypatch.setattr(httpx, "post", boom)
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openrouter")
    monkeypatch.setenv("EMBEDDING_MODEL", "mongodb/voyage-4-lite")
    assert main(["embed", "--live"]) == 2
    error = capsys.readouterr().err
    assert "OPENROUTER_API_KEY" in error
    assert "No request was sent" in error
