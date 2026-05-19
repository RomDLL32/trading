import pytest

from alpaca_trader.config import Settings


def test_from_env_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in [
        "APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "APCA_API_BASE_URL",
        "TRADING_UNIVERSE", "TRADING_SMA_FAST", "TRADING_SMA_SLOW",
        "TRADING_TARGET_WEIGHT", "TRADING_MAX_GROSS_EXPOSURE",
    ]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("APCA_API_KEY_ID", "k")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "s")

    s = Settings.from_env()
    assert s.paper is True
    assert s.sma_fast == 10
    assert s.sma_slow == 30
    assert "SPY" in s.universe


def test_require_credentials_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APCA_API_KEY_ID", "")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "")
    s = Settings.from_env()
    with pytest.raises(RuntimeError, match="credentials missing"):
        s.require_credentials()


def test_rejects_invalid_sma_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APCA_API_KEY_ID", "k")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "s")
    monkeypatch.setenv("TRADING_SMA_FAST", "30")
    monkeypatch.setenv("TRADING_SMA_SLOW", "10")
    with pytest.raises(ValueError):
        Settings.from_env()
