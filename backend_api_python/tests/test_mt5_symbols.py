"""Tests for MT5 symbol normalization."""

from app.services.mt5_trading.symbols import normalize_symbol


def test_normalize_symbol_plain_forex():
    assert normalize_symbol("eurusd") == "EURUSD"
    assert normalize_symbol("EUR/USD") == "EURUSD"


def test_normalize_symbol_preserves_dotted_suffix_case():
    assert normalize_symbol("EURUSD.z") == "EURUSD.z"
    assert normalize_symbol("eurusd.z") == "EURUSD.z"
    assert normalize_symbol("EURUSD.raw") == "EURUSD.raw"


def test_normalize_symbol_broker_suffix_append():
    assert normalize_symbol("eurusd", broker_suffix="m") == "EURUSDm"
