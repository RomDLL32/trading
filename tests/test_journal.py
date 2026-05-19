import json
from pathlib import Path

import pytest

from alpaca_trader import cli


def _settings():
    # cli.cmd_journal_* don't touch settings, so a sentinel is fine.
    return object()


def _run(argv: list[str]) -> int:
    parser = cli._build_parser()
    args = parser.parse_args(argv)
    return args.fn(_settings(), args)


def test_tail_empty_journal(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    path = tmp_path / "j.jsonl"
    _run(["journal-tail", "--path", str(path)])
    out = json.loads(capsys.readouterr().out)
    assert out["entries"] == []
    assert "first run" in out["note"]


def test_append_then_tail_roundtrip(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    path = tmp_path / "j.jsonl"
    entry = {"session_id": "s1", "decisions": [{"symbol": "AAPL", "action": "buy"}]}

    _run(["journal-append", "--entry", json.dumps(entry), "--path", str(path)])
    capsys.readouterr()  # discard

    _run(["journal-tail", "-n", "10", "--path", str(path)])
    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1
    assert out["entries"][0]["session_id"] == "s1"
    assert "timestamp" in out["entries"][0]  # auto-added


def test_tail_returns_only_last_n(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    path = tmp_path / "j.jsonl"
    for i in range(5):
        _run(["journal-append", "--entry", json.dumps({"i": i}), "--path", str(path)])
        capsys.readouterr()

    _run(["journal-tail", "-n", "2", "--path", str(path)])
    out = json.loads(capsys.readouterr().out)
    assert [e["i"] for e in out["entries"]] == [3, 4]


def test_append_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "j.jsonl"
    with pytest.raises(SystemExit, match="valid JSON"):
        _run(["journal-append", "--entry", "{not json", "--path", str(path)])


def test_append_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "j.jsonl"
    with pytest.raises(SystemExit, match="JSON object"):
        _run(["journal-append", "--entry", "[1,2,3]", "--path", str(path)])
