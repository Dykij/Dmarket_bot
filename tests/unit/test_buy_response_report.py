"""_parse_buy_response: what the log must say about an offers-buy answer.

Spec v2.0.0 entity.OfferBuyResponse: status TxPending|TxSuccess|TxFailed,
orderId, txId, dmOffersFailReason{code}, dmOffersStatus{offerId: {started}}.
No item ids in the answer. Success/failure semantics are unchanged by this
step (started offers succeed, TxFailed fails); only the reporting is added.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from src.core.target_sniping.execution import _ExecutionMixin

LOGGER = "SnipingBot"


def _buys(*ids: str) -> list[dict]:
    return [{"buy_offer": {"offerId": i}} for i in ids]


def _parse(resp: dict, *ids: str):
    return _ExecutionMixin._parse_buy_response(SimpleNamespace(), resp, _buys(*ids))


def test_success_log_carries_order_and_tx_ids(caplog) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    ok, bought = _parse(
        {"status": "TxSuccess", "orderId": "ord-77", "txId": "tx-88",
         "dmOffersStatus": {"o1": {"started": True}}},
        "o1",
    )
    assert ok == {"o1"} and bought == []
    assert "ord-77" in caplog.text and "tx-88" in caplog.text


def test_tx_pending_still_succeeds_but_is_flagged(caplog) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    ok, _ = _parse(
        {"status": "TxPending", "orderId": "ord-1", "txId": "tx-1",
         "dmOffersStatus": {"o1": {"started": True}}},
        "o1",
    )
    assert ok == {"o1"}  # semantics unchanged
    assert "TxPending" in caplog.text and "not final" in caplog.text.lower()


def test_started_false_offer_is_excluded() -> None:
    ok, _ = _parse(
        {"status": "TxSuccess", "orderId": "a", "txId": "b",
         "dmOffersStatus": {"o1": {"started": True}, "o2": {"started": False}}},
        "o1", "o2",
    )
    assert ok == {"o1"}


def test_missing_dm_offers_status_warns_and_keeps_legacy_all_success(caplog) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    ok, _ = _parse({"status": "TxSuccess", "orderId": "a", "txId": "b"}, "o1", "o2")
    assert ok == {"o1", "o2"}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("dmOffersStatus" in r.getMessage() for r in warnings)


def test_unrecognized_status_warns_and_keeps_legacy_rule(caplog) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    ok, _ = _parse({"status": "OK"}, "o1")
    assert ok == {"o1"}  # legacy: any non-empty status except TxFailed
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("unrecognized" in r.getMessage().lower() for r in warnings)


def test_tx_failed_fails_everything_and_logs_reason(caplog) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    ok, _ = _parse(
        {"status": "TxFailed", "orderId": "a", "txId": "b",
         "dmOffersFailReason": {"code": "BalanceInsufficientFunds"},
         "dmOffersStatus": {"o1": {"started": True}}},
        "o1",
    )
    assert ok == set()
    assert "BalanceInsufficientFunds" in caplog.text
