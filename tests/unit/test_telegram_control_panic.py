"""Unit tests for /panic command (src/telegram/control_bot/commands/control.py).

Part 2: Characterization & Red Tests.
Testing contract (C1-C5):
1. Exactly one report message sent with parse_mode=None (kwargs['parse_mode'] is None).
   Lines: stop_ok (yes|no), confirmed, failed, unconfirmed, unknown, not_sent,
   simulated, skipped_no_id, list_complete (yes|no), failure_codes.
2. Last message verdict: "You are safe" ONLY if list_complete=yes, stop_ok=yes,
   and all non-confirmed counts are 0 (failed = unconfirmed = unknown = not_sent =
   simulated = skipped_no_id = 0); otherwise "NOT confirmed" and "DMarket" in last message,
   and "You are safe" must not appear in any message.
3. Invariants: No "Internal error" in any message; if "Cancelled N" appears, N == confirmed.
   C5: No message contains exception text (e.g. "boom").
4. Empty list: "No active offers" in message, confirmed: 0, list_complete: yes, verdict safe.
5. Deletion starts after all pages are fetched (all list calls before first delete),
   chunk size 100, no retries of failed chunks on delete.
6. C1 & C2 (R10): Exception from state.stop() does not abort /panic; logged, offers
   cancelled as usual, stop_ok: no in report, verdict unsafe. If stop() returns False,
   that is not an error (stop_ok: yes).
7. C4: failed[] entries matched by offerId OR by assetId (attributes.id) with whitespace
   stripping; failed[] has priority over offers[].
"""

from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import types

from src.api.dmarket_api_client.backoff import CircuitOpenError
from src.telegram.control_bot.commands.control import cmd_panic


class CallTracker:
    """Tracks sequence and order of operations across state and API calls."""

    def __init__(self) -> None:
        self.seq = 0
        self.calls: list[dict[str, Any]] = []

    def log(self, name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.seq += 1
        entry = {"seq": self.seq, "name": name, "args": args, "kwargs": kwargs}
        self.calls.append(entry)
        return entry


def extract_cursor(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str | None:
    """Extract cursor parameter from get_user_offers_v2 invocation."""
    if "cursor" in kwargs:
        return kwargs["cursor"]
    if len(args) > 2:
        return args[2]
    return None


def make_mock_client(
    tracker: CallTracker,
    list_responses: Any = None,
    batch_responses: Any = None,
) -> MagicMock:
    """Create a mock DMarketAPIClient with tracked calls and customizable responses."""
    client = MagicMock()
    list_calls: list[dict[str, Any]] = []
    delete_calls: list[dict[str, Any]] = []

    list_idx = [0]

    async def mock_get_user_offers(*args: Any, **kwargs: Any) -> Any:
        cursor = extract_cursor(args, kwargs)
        log_kwargs = dict(kwargs)
        log_kwargs["cursor"] = cursor
        entry = tracker.log("get_user_offers_v2", *args, **log_kwargs)
        list_calls.append(entry)

        if callable(list_responses):
            call_kwargs = {k: v for k, v in kwargs.items() if k != "cursor"}
            res = list_responses(*args, cursor=cursor, **call_kwargs)
            if isinstance(res, Exception):
                raise res
            return res
        if isinstance(list_responses, Exception):
            raise list_responses
        if isinstance(list_responses, dict):
            return list_responses
        if isinstance(list_responses, list):
            if list_idx[0] < len(list_responses):
                res = list_responses[list_idx[0]]
                list_idx[0] += 1
                if isinstance(res, Exception):
                    raise res
                return res
            return {"items": []}
        return {"items": []}

    delete_idx = [0]

    async def mock_batch_delete(*args: Any, **kwargs: Any) -> Any:
        offer_ids = args[0] if args else kwargs.get("offer_ids", [])
        log_kwargs = dict(kwargs)
        log_kwargs["offer_ids"] = offer_ids
        entry = tracker.log("batch_delete_offers_v2", *args, **log_kwargs)
        delete_calls.append(entry)

        if callable(batch_responses):
            call_kwargs = {k: v for k, v in kwargs.items() if k != "offer_ids"}
            res = batch_responses(*args, offer_ids=offer_ids, **call_kwargs)
            if isinstance(res, Exception):
                raise res
            return res
        if isinstance(batch_responses, Exception):
            raise batch_responses
        if isinstance(batch_responses, dict):
            return batch_responses
        if isinstance(batch_responses, list):
            if delete_idx[0] < len(batch_responses):
                res = batch_responses[delete_idx[0]]
                delete_idx[0] += 1
                if isinstance(res, Exception):
                    raise res
                return res
            return {"offers": [{"id": oid} for oid in offer_ids]}
        return {"offers": [{"id": oid} for oid in offer_ids]}

    close_mock = AsyncMock()

    async def mock_close(*args: Any, **kwargs: Any) -> None:
        tracker.log("close", *args, **kwargs)
        await close_mock(*args, **kwargs)

    client.get_user_offers_v2 = AsyncMock(side_effect=mock_get_user_offers)
    client.batch_delete_offers_v2 = AsyncMock(side_effect=mock_batch_delete)
    client.close = AsyncMock(side_effect=mock_close)
    client._close_mock = close_mock
    client._list_calls = list_calls
    client._delete_calls = delete_calls
    return client


def make_state(
    client: Any = None,
    tracker: CallTracker | None = None,
    stop_side_effect: Any = None,
) -> SimpleNamespace:
    """Create a state object matching control.BotState."""
    stop_mock = AsyncMock(return_value=True, side_effect=stop_side_effect)
    if tracker is not None:
        orig_stop = stop_mock

        async def tracked_stop(*args: Any, **kwargs: Any) -> Any:
            tracker.log("state_stop", *args, **kwargs)
            return await orig_stop(*args, **kwargs)

        stop_mock = AsyncMock(side_effect=tracked_stop)

    return SimpleNamespace(
        lock=asyncio.Lock(),
        client=client,
        stop=stop_mock,
    )


def make_message() -> AsyncMock:
    """Create a mock aiogram Message."""
    msg = AsyncMock(spec=types.Message)
    msg.from_user = MagicMock()
    msg.from_user.id = 12345
    msg.answer = AsyncMock()
    return msg


REPORT_CONFIRMED_RE = re.compile(r"(?m)^\s*confirmed:")


def parse_report(message_mock: AsyncMock) -> dict[str, Any]:
    r"""Parse the single report message from message.answer calls.

    Raises AssertionError if report message matching '(?m)^\s*confirmed:' is not found.
    """
    calls = message_mock.answer.call_args_list
    report_candidates = []
    for call in calls:
        args, kwargs = call
        text = args[0] if args else kwargs.get("text", "")
        if REPORT_CONFIRMED_RE.search(text):
            report_candidates.append((text, kwargs))

    if not report_candidates:
        sent_texts = [c[0][0] if c[0] else c[1].get("text", "") for c in calls]
        raise AssertionError(
            f"Report message matching '(?m)^\\s*confirmed:' was not found in message.answer calls. "
            f"Total calls: {len(calls)}. Sent texts: {sent_texts}"
        )
    if len(report_candidates) > 1:
        raise AssertionError(f"Expected exactly one report message, found {len(report_candidates)}")

    report_text, report_kwargs = report_candidates[0]

    if "parse_mode" not in report_kwargs or report_kwargs["parse_mode"] is not None:
        raise AssertionError(
            f"Report message kwargs must contain 'parse_mode'=None, got: {report_kwargs.get('parse_mode')!r} (kwargs: {report_kwargs})"
        )

    lines = [line.strip() for line in report_text.strip().splitlines() if line.strip()]
    data: dict[str, str] = {}
    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip()

    required_keys = [
        "stop_ok",
        "confirmed",
        "failed",
        "unconfirmed",
        "unknown",
        "not_sent",
        "simulated",
        "skipped_no_id",
        "list_complete",
        "failure_codes",
    ]
    for key in required_keys:
        if key not in data:
            raise AssertionError(f"Report missing required key '{key}'. Full report:\n{report_text}")

    parsed: dict[str, Any] = {}
    parsed["stop_ok"] = data["stop_ok"]
    if parsed["stop_ok"] not in ("yes", "no"):
        raise AssertionError(f"stop_ok must be 'yes' or 'no', got: {parsed['stop_ok']!r}")

    for k in [
        "confirmed",
        "failed",
        "unconfirmed",
        "unknown",
        "not_sent",
        "simulated",
        "skipped_no_id",
    ]:
        try:
            parsed[k] = int(data[k])
        except ValueError:
            raise AssertionError(f"Report key '{k}' must be integer, got: {data[k]!r}")

    parsed["list_complete"] = data["list_complete"]
    if parsed["list_complete"] not in ("yes", "no"):
        raise AssertionError(f"list_complete must be 'yes' or 'no', got: {parsed['list_complete']!r}")

    parsed["failure_codes"] = data["failure_codes"]
    parsed["_text"] = report_text
    return parsed


def assert_contract_invariants(message_mock: AsyncMock, report: dict[str, Any]) -> None:
    """Verify invariants across all sent messages."""
    calls = message_mock.answer.call_args_list
    confirmed = report["confirmed"]
    cancelled_pattern = re.compile(r"Cancelled\s+(\d+)", re.IGNORECASE)
    for call in calls:
        args, kwargs = call
        text = args[0] if args else kwargs.get("text", "")
        if "Internal error" in text:
            raise AssertionError(f"Found 'Internal error' in message: {text!r}")
        if "boom" in text:
            raise AssertionError(f"Found exception text 'boom' in message: {text!r}")
        match = cancelled_pattern.search(text)
        if match:
            cnt = int(match.group(1))
            if cnt != confirmed:
                raise AssertionError(f"Message has 'Cancelled {cnt}', but confirmed={confirmed} in report")


def assert_verdict(message_mock: AsyncMock, report: dict[str, Any], expected_safe: bool) -> None:
    """Verify verdict message content and safety claims."""
    calls = message_mock.answer.call_args_list
    if not calls:
        raise AssertionError("No messages were sent")
    last_args, last_kwargs = calls[-1]
    last_text = last_args[0] if last_args else last_kwargs.get("text", "")
    all_texts = [c[0][0] if c[0] else c[1].get("text", "") for c in calls]

    is_safe = (
        report["list_complete"] == "yes"
        and report["stop_ok"] == "yes"
        and report["failed"] == 0
        and report["unconfirmed"] == 0
        and report["unknown"] == 0
        and report["not_sent"] == 0
        and report["simulated"] == 0
        and report["skipped_no_id"] == 0
    )
    if is_safe != expected_safe:
        raise AssertionError(
            f"Calculated is_safe={is_safe} does not match expected_safe={expected_safe} for report: {report}"
        )

    if expected_safe:
        if "You are safe" not in last_text:
            raise AssertionError(f"Expected safe verdict containing 'You are safe', got: {last_text!r}")
    else:
        for t in all_texts:
            if "You are safe" in t:
                raise AssertionError(f"Unsafe scenario must NOT contain 'You are safe' in any message, found in: {t!r}")
        if "NOT confirmed" not in last_text or "DMarket" not in last_text:
            raise AssertionError(
                f"Expected unsafe verdict containing 'NOT confirmed' and 'DMarket', got: {last_text!r}"
            )


@pytest.fixture(autouse=True)
def setup_panic_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure safe mocks for all tests so real client and network are never used."""
    monkeypatch.setattr(
        "src.telegram.control_bot.commands.control.DMarketAPIClient",
        MagicMock(side_effect=AssertionError("real client constructed")),
    )
    mock_config = MagicMock()
    mock_config.GAME_ID = "test-game"
    mock_config.PUBLIC_KEY = "pk-test"
    monkeypatch.setattr("src.telegram.control_bot.commands.control.Config", mock_config)
    monkeypatch.setattr(
        "src.telegram.control_bot.resilience.get_dmarket_secret",
        lambda: "sec-test",
    )


# ==============================================================================
# Matrix Tests (T01 - T20)
# ==============================================================================


@pytest.mark.asyncio
async def test_panic_three_pages_pagination_and_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    """T01: 3 pages (100, 100, 50). All list calls before first delete; chunks of 100."""
    tracker = CallTracker()
    page1 = {
        "items": [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(100)],
        "cursor": "c1",
    }
    page2 = {
        "items": [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(100, 200)],
        "cursor": "c2",
    }
    page3 = {
        "items": [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(200, 250)],
    }

    client = make_mock_client(tracker, list_responses=[page1, page2, page3])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    # 3 list calls with cursors [None, "c1", "c2"]
    assert len(client._list_calls) == 3
    assert client._list_calls[0]["kwargs"]["cursor"] is None
    assert client._list_calls[1]["kwargs"]["cursor"] == "c1"
    assert client._list_calls[2]["kwargs"]["cursor"] == "c2"

    # All list calls must occur before first delete call
    assert len(client._delete_calls) == 3
    last_list_seq = client._list_calls[-1]["seq"]
    first_del_seq = client._delete_calls[0]["seq"]
    assert last_list_seq < first_del_seq, "All list calls must occur before first delete call"

    # Delete calls chunks: 100, 100, 50
    del_chunk_sizes = [len(call["kwargs"]["offer_ids"]) for call in client._delete_calls]
    assert del_chunk_sizes == [100, 100, 50]

    # Union of ids: o0..o249, each exactly once
    all_deleted_ids = []
    for call in client._delete_calls:
        all_deleted_ids.extend(call["kwargs"]["offer_ids"])
    expected_ids = [f"o{i}" for i in range(250)]
    assert all_deleted_ids == expected_ids

    report = parse_report(msg)
    assert report["confirmed"] == 250
    assert report["list_complete"] == "yes"
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=True)


@pytest.mark.asyncio
async def test_panic_empty_cursor_ends_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    """T02: Empty cursor string ends pagination."""
    tracker = CallTracker()
    page1 = {
        "items": [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(5)],
        "cursor": "",
    }
    client = make_mock_client(tracker, list_responses=[page1])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert len(client._list_calls) == 1
    report = parse_report(msg)
    assert report["confirmed"] == 5
    assert report["list_complete"] == "yes"
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=True)


@pytest.mark.asyncio
async def test_panic_empty_offers_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """T03: Empty offers list -> batch not called, 'No active offers', safe verdict."""
    tracker = CallTracker()
    client = make_mock_client(tracker, list_responses=[{"items": []}])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert len(client._delete_calls) == 0
    all_texts = [c[0][0] if c[0] else c[1].get("text", "") for c in msg.answer.call_args_list]
    assert any("No active offers" in t for t in all_texts), f"Expected 'No active offers' in texts: {all_texts}"

    report = parse_report(msg)
    assert report["confirmed"] == 0
    assert report["list_complete"] == "yes"
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=True)


@pytest.mark.asyncio
async def test_panic_cursor_repeat_stops_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    """T04: Repeating cursor stops pagination to avoid infinite loops."""
    tracker = CallTracker()
    page1 = {
        "items": [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(10)],
        "cursor": "c1",
    }
    page2 = {
        "items": [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(10, 20)],
        "cursor": "c1",  # Repeated cursor
    }
    page3 = {
        "items": [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(20, 30)],
        "cursor": "c3",
    }

    client = make_mock_client(tracker, list_responses=[page1, page2, page3])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    # Exactly 2 list calls; page 3 must not be requested
    assert len(client._list_calls) == 2

    # Exactly 1 batch delete with gathered 20 offers
    assert len(client._delete_calls) == 1
    assert client._delete_calls[0]["kwargs"]["offer_ids"] == [f"o{i}" for i in range(20)]

    report = parse_report(msg)
    assert report["list_complete"] == "no"
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=False)


@pytest.mark.asyncio
async def test_panic_page_limit_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    """T05: Page limit enforced at 100 pages when API returns infinite pages."""
    tracker = CallTracker()
    page_count = 0

    def infinite_pages(*args: Any, cursor: str | None = None, **kwargs: Any) -> dict[str, Any]:
        nonlocal page_count
        curr = page_count
        page_count += 1
        return {
            "items": [{"offerId": f"o{curr}", "attributes": {"id": f"A{curr}"}}],
            "cursor": f"c{curr + 1}",
        }

    client = make_mock_client(tracker, list_responses=infinite_pages)
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert len(client._list_calls) == 100
    assert len(client._delete_calls) == 1
    delete_ids = client._delete_calls[0]["kwargs"]["offer_ids"]
    assert len(delete_ids) == 100
    assert len(set(delete_ids)) == 100

    report = parse_report(msg)
    assert report["list_complete"] == "no"
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first_page_payload",
    [{}, None, [], "x", {"items": "bad"}, {"items": None}],
)
async def test_panic_invalid_items_first_page(
    monkeypatch: pytest.MonkeyPatch, first_page_payload: Any
) -> None:
    """T06: First page without a valid items list stops listing without delete call."""
    tracker = CallTracker()
    client = make_mock_client(tracker, list_responses=[first_page_payload])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert len(client._list_calls) == 1
    assert len(client._delete_calls) == 0

    report = parse_report(msg)
    assert report["list_complete"] == "no"
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=False)


@pytest.mark.asyncio
async def test_panic_garbage_elements_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """T07: Malformed items on a page are skipped and reported in skipped_no_id."""
    tracker = CallTracker()
    raw_items = [
        {"offerId": "o1", "attributes": {"id": "A1"}},
        {"offerId": "  "},
        {},
        "str",
        None,
        5,
        {"offerId": 777},
    ]
    client = make_mock_client(tracker, list_responses=[{"items": raw_items}])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert len(client._delete_calls) == 1
    assert client._delete_calls[0]["kwargs"]["offer_ids"] == ["o1", "777"]

    report = parse_report(msg)
    assert report["skipped_no_id"] == 5
    assert report["confirmed"] == 2
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=False)


@pytest.mark.asyncio
async def test_panic_deduplication_and_strip(monkeypatch: pytest.MonkeyPatch) -> None:
    """T08: Whitespace stripping and deduplication preserving order of first appearance."""
    tracker = CallTracker()
    page1 = {
        "items": [
            {"offerId": "o1", "attributes": {"id": "A1"}},
            {"offerId": " o1 ", "attributes": {"id": "A1"}},
            {"offerId": "o2", "attributes": {"id": "A2"}},
        ],
        "cursor": "c1",
    }
    page2 = {
        "items": [
            {"offerId": "o2", "attributes": {"id": "A2"}},
            {"offerId": "o3", "attributes": {"id": "A3"}},
        ],
    }
    client = make_mock_client(tracker, list_responses=[page1, page2])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert len(client._delete_calls) == 1
    assert client._delete_calls[0]["kwargs"]["offer_ids"] == ["o1", "o2", "o3"]

    report = parse_report(msg)
    assert report["confirmed"] == 3
    assert report["skipped_no_id"] == 0
    assert report["list_complete"] == "yes"
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=True)


@pytest.mark.asyncio
async def test_panic_failed_priority_over_offers(monkeypatch: pytest.MonkeyPatch) -> None:
    """T09: Entries in failed[] override presence in offers[]."""
    tracker = CallTracker()
    items = [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(5)]
    batch_resp = {
        "offers": [{"id": f"o{i}"} for i in range(5)],
        "failed": [{"offerId": "o2", "code": "OFFER_LOCKED"}],
    }

    client = make_mock_client(tracker, list_responses=[{"items": items}], batch_responses=[batch_resp])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    report = parse_report(msg)
    assert report["confirmed"] == 4
    assert report["failed"] == 1
    assert report["unconfirmed"] == 0
    assert "OFFER_LOCKED" in report["_text"]
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=False)


@pytest.mark.asyncio
async def test_panic_unconfirmed_offers(monkeypatch: pytest.MonkeyPatch) -> None:
    """T10: Offers not found in either offers[] or failed[] count as unconfirmed."""
    tracker = CallTracker()
    items = [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(3)]
    batch_resp = {"offers": [{"id": "o0"}]}

    client = make_mock_client(tracker, list_responses=[{"items": items}], batch_responses=[batch_resp])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    report = parse_report(msg)
    assert report["confirmed"] == 1
    assert report["unconfirmed"] == 2
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=False)


@pytest.mark.asyncio
async def test_panic_confirm_by_asset_id_and_strip(monkeypatch: pytest.MonkeyPatch) -> None:
    """T11: Confirmation by assetId and whitespace stripping."""
    tracker = CallTracker()
    items = [
        {"offerId": "o1", "attributes": {"id": "A1"}},
        {"offerId": "o2", "attributes": {"id": "A2"}},
    ]
    batch_resp = {
        "offers": [{"assetId": " A1 "}, {"id": " o2 "}],
    }

    client = make_mock_client(tracker, list_responses=[{"items": items}], batch_responses=[batch_resp])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    report = parse_report(msg)
    assert report["confirmed"] == 2
    assert report["unconfirmed"] == 0
    assert report["failed"] == 0
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_batch_resp",
    [None, [], "ok", 42, {"offers": "x", "failed": {"offerId": "o0"}}],
)
async def test_panic_garbage_batch_response(
    monkeypatch: pytest.MonkeyPatch, bad_batch_resp: Any
) -> None:
    """T12: Malformed batch response treats all chunk items as unconfirmed."""
    tracker = CallTracker()
    items = [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(3)]
    client = make_mock_client(
        tracker, list_responses=[{"items": items}], batch_responses=[bad_batch_resp]
    )
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    report = parse_report(msg)
    assert report["confirmed"] == 0
    assert report["unconfirmed"] == 3
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc_factory",
    [lambda: RuntimeError("boom"), lambda: TimeoutError()],
)
async def test_panic_exception_on_chunk(
    monkeypatch: pytest.MonkeyPatch, exc_factory: Any
) -> None:
    """T13: Exception on second chunk continues next chunks; items counted as unknown."""
    tracker = CallTracker()
    items = [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(250)]

    def batch_responses(*args: Any, offer_ids: list[str], **kwargs: Any) -> Any:
        # Second chunk corresponds to ids o100..o199
        if "o100" in offer_ids:
            raise exc_factory()
        return {"offers": [{"id": oid} for oid in offer_ids]}

    client = make_mock_client(tracker, list_responses=[{"items": items}], batch_responses=batch_responses)
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    # Exactly 3 delete calls
    assert len(client._delete_calls) == 3

    # Second chunk ids (o100-o199) passed exactly once across all delete calls (no retries)
    all_deleted_ids = []
    for call in client._delete_calls:
        all_deleted_ids.extend(call["kwargs"]["offer_ids"])
    chunk2_ids = [f"o{i}" for i in range(100, 200)]
    for cid in chunk2_ids:
        assert all_deleted_ids.count(cid) == 1

    report = parse_report(msg)
    assert report["confirmed"] == 150
    assert report["unknown"] == 100
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=False)


@pytest.mark.asyncio
async def test_panic_circuit_breaker_on_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    """T14: CircuitOpenError halts subsequent chunks; unattempted counted as not_sent."""
    tracker = CallTracker()
    items = [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(250)]

    def batch_responses(*args: Any, offer_ids: list[str], **kwargs: Any) -> Any:
        if "o100" in offer_ids:
            raise CircuitOpenError(breaker_name="dmarket_api", cooldown_remaining=30.0)
        return {"offers": [{"id": oid} for oid in offer_ids]}

    client = make_mock_client(tracker, list_responses=[{"items": items}], batch_responses=batch_responses)
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    # Exactly 2 delete calls (chunk 1 and chunk 2 which tripped breaker; chunk 3 aborted)
    assert len(client._delete_calls) == 2

    report = parse_report(msg)
    assert report["confirmed"] == 100
    assert report["not_sent"] == 150
    assert report["unknown"] == 0
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=False)


@pytest.mark.asyncio
async def test_panic_exception_on_reading_page_two(monkeypatch: pytest.MonkeyPatch) -> None:
    """T15: Exception on reading page 2 still deletes gathered items from page 1."""
    tracker = CallTracker()
    page1 = {
        "items": [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(100)],
        "cursor": "c1",
    }
    client = make_mock_client(tracker, list_responses=[page1, RuntimeError("boom")])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    # 2 list calls
    assert len(client._list_calls) == 2

    # 1 batch delete with 100 gathered ids
    assert len(client._delete_calls) == 1
    assert client._delete_calls[0]["kwargs"]["offer_ids"] == [f"o{i}" for i in range(100)]

    report = parse_report(msg)
    assert report["confirmed"] == 100
    assert report["list_complete"] == "no"
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=False)


@pytest.mark.asyncio
async def test_panic_dry_run_simulation(monkeypatch: pytest.MonkeyPatch) -> None:
    """T16: DRY_RUN simulation response recognized as simulated."""
    tracker = CallTracker()
    items = [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(150)]
    sim_resp = {"status": "success", "simulated": True, "message": "Simulation Mode Active"}

    client = make_mock_client(tracker, list_responses=[{"items": items}], batch_responses=sim_resp)
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert len(client._delete_calls) == 2
    assert [len(c["kwargs"]["offer_ids"]) for c in client._delete_calls] == [100, 50]

    report = parse_report(msg)
    assert report["simulated"] == 150
    assert report["confirmed"] == 0
    assert "simulated" in report["_text"].lower()
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=False)


@pytest.mark.asyncio
async def test_panic_failure_codes_limit_and_plain_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """T17: Failure codes limit (up to 5 codes) and report sent as plain text."""
    tracker = CallTracker()
    items = [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(7)]
    codes = ["CODE_A", "CODE_B", "CODE_C", "CODE_D", "CODE_E", "CODE_F"]
    failed_entries = [{"offerId": f"o{i}", "code": codes[i]} for i in range(6)]
    failed_entries.append({"offerId": "o6"})  # 1 without error code

    batch_resp = {"offers": [], "failed": failed_entries}
    client = make_mock_client(tracker, list_responses=[{"items": items}], batch_responses=[batch_resp])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    report = parse_report(msg)
    assert report["failed"] == 7

    # failure_codes should contain 1 to 5 codes
    raw_codes = [c.strip() for c in report["failure_codes"].split(",") if c.strip() and c.strip() != "-"]
    assert 1 <= len(raw_codes) <= 5
    assert set(raw_codes) <= set(codes)

    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["normal", "error"])
async def test_panic_temporary_client_cleanup(
    monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    """T18: Temporary client created when state.client is None; closed and reset in finally."""
    tracker = CallTracker()
    if scenario == "normal":
        items = [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(3)]
        mock_client = make_mock_client(tracker, list_responses=[{"items": items}])
    else:
        mock_client = make_mock_client(tracker, list_responses=RuntimeError("boom"))

    created_clients: list[MagicMock] = []

    def mock_client_factory(*args: Any, **kwargs: Any) -> MagicMock:
        created_clients.append(mock_client)
        return mock_client

    monkeypatch.setattr(
        "src.telegram.control_bot.commands.control.DMarketAPIClient",
        mock_client_factory,
    )

    state = make_state(client=None, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert len(created_clients) == 1
    assert mock_client._close_mock.await_count == 1
    assert state.client is None


@pytest.mark.asyncio
async def test_panic_shared_client_not_touched(monkeypatch: pytest.MonkeyPatch) -> None:
    """T19: Shared client in state.client is not closed and not recreated."""
    tracker = CallTracker()
    items = [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(2)]
    mock_client = make_mock_client(tracker, list_responses=[{"items": items}])

    client_factory_called = [False]

    def mock_client_factory(*args: Any, **kwargs: Any) -> MagicMock:
        client_factory_called[0] = True
        return mock_client

    monkeypatch.setattr(
        "src.telegram.control_bot.commands.control.DMarketAPIClient",
        mock_client_factory,
    )

    state = make_state(client=mock_client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert not client_factory_called[0]
    assert mock_client._close_mock.await_count == 0
    assert state.client is mock_client


@pytest.mark.asyncio
async def test_panic_stop_awaited_before_first_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """T20: state.stop awaited exactly once and strictly before first list call."""
    tracker = CallTracker()
    items = [{"offerId": "o1", "attributes": {"id": "A1"}}]
    mock_client = make_mock_client(tracker, list_responses=[{"items": items}])

    state = make_state(client=mock_client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert state.stop.await_count == 1

    stop_calls = [c for c in tracker.calls if c["name"] == "state_stop"]
    list_calls = [c for c in tracker.calls if c["name"] == "get_user_offers_v2"]

    assert len(stop_calls) == 1
    assert len(list_calls) >= 1
    assert stop_calls[0]["seq"] < list_calls[0]["seq"], "state.stop must be awaited before get_user_offers_v2"


@pytest.mark.asyncio
async def test_panic_stop_exception_still_cancels_offers(monkeypatch: pytest.MonkeyPatch) -> None:
    """T21: Exception from state.stop() does not abort panic; offers cancelled, stop_ok=no."""
    tracker = CallTracker()
    items = [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(3)]
    client = make_mock_client(tracker, list_responses=[{"items": items}])
    state = make_state(
        client=client,
        tracker=tracker,
        stop_side_effect=RuntimeError("stop boom"),
    )
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert len(client._list_calls) >= 1
    assert len(client._delete_calls) == 1
    assert client._delete_calls[0]["kwargs"]["offer_ids"] == ["o0", "o1", "o2"]
    assert state.stop.await_count == 1

    report = parse_report(msg)
    assert report["confirmed"] == 3
    assert report["stop_ok"] == "no"
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=False)


@pytest.mark.asyncio
async def test_panic_failed_matched_by_asset_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """T23: Entries in failed[] matched by assetId (attributes.id) with whitespace strip."""
    tracker = CallTracker()
    items = [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(3)]
    batch_resp = {
        "offers": [{"id": "o0"}, {"id": "o1"}, {"id": "o2"}],
        "failed": [{"assetId": " A1 ", "code": "OFFER_LOCKED"}],
    }

    client = make_mock_client(tracker, list_responses=[{"items": items}], batch_responses=[batch_resp])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    report = parse_report(msg)
    assert report["confirmed"] == 2
    assert report["failed"] == 1
    assert report["unconfirmed"] == 0
    assert "OFFER_LOCKED" in report["_text"]
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=False)


# ==============================================================================
# Helper Unit Tests (H1 - H3)
# ==============================================================================


@pytest.mark.asyncio
async def test_helper_callable_list_response_accepts_cursor_keyword_and_positional() -> None:
    """H1: mock_get_user_offers accepts cursor both keyword and positional without duplicate kwargs."""
    tracker = CallTracker()
    client = make_mock_client(
        tracker,
        list_responses=lambda *a, cursor=None, **k: {"seen": cursor},
    )
    r1 = await client.get_user_offers_v2("g", limit=100, cursor="c9")
    assert r1 == {"seen": "c9"}
    r2 = await client.get_user_offers_v2("g", 100, "c8")
    assert r2 == {"seen": "c8"}
    r3 = await client.get_user_offers_v2("g", limit=100)
    assert r3 == {"seen": None}


@pytest.mark.asyncio
async def test_helper_callable_batch_response_accepts_offer_ids_positional_and_keyword() -> None:
    """H2: mock_batch_delete accepts offer_ids both keyword and positional without duplicate kwargs."""
    tracker = CallTracker()
    client = make_mock_client(
        tracker,
        batch_responses=lambda *a, offer_ids, **k: {"n": len(offer_ids)},
    )
    r1 = await client.batch_delete_offers_v2(["a", "b"])
    assert r1 == {"n": 2}
    r2 = await client.batch_delete_offers_v2(offer_ids=["a"])
    assert r2 == {"n": 1}
    assert client._delete_calls[0]["kwargs"]["offer_ids"] == ["a", "b"]
    assert client._delete_calls[1]["kwargs"]["offer_ids"] == ["a"]


@pytest.mark.asyncio
async def test_helper_dict_batch_response_repeats_for_every_call() -> None:
    """H3: dict batch_responses is returned repeatedly for every delete call."""
    tracker = CallTracker()
    resp = {"status": "ok", "repeated": True}
    client = make_mock_client(tracker, batch_responses=resp)
    r1 = await client.batch_delete_offers_v2(["o1"])
    r2 = await client.batch_delete_offers_v2(["o2"])
    assert r1 == resp
    assert r2 == resp


@pytest.mark.asyncio
async def test_panic_stop_returns_false_is_not_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """G1: stop() returning False means bot was not running, which is not an error (stop_ok=yes)."""
    tracker = CallTracker()
    items = [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(3)]
    client = make_mock_client(tracker, list_responses=[{"items": items}])
    state = make_state(
        client=client,
        tracker=tracker,
        stop_side_effect=lambda *a, **k: False,
    )
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert state.stop.await_count == 1
    assert len(client._list_calls) == 1
    assert len(client._delete_calls) == 1
    assert client._delete_calls[0]["kwargs"]["offer_ids"] == ["o0", "o1", "o2"]

    report = parse_report(msg)
    assert report["stop_ok"] == "yes"
    assert report["confirmed"] == 3
    assert report["failed"] == 0
    assert report["unconfirmed"] == 0
    assert report["unknown"] == 0
    assert report["not_sent"] == 0
    assert report["simulated"] == 0
    assert report["skipped_no_id"] == 0
    assert report["list_complete"] == "yes"

    assert_verdict(msg, report, expected_safe=True)
    calls = msg.answer.call_args_list
    assert len(calls) > 0
    last_text = calls[-1][0][0] if calls[-1][0] else calls[-1][1].get("text", "")
    all_texts = [c[0][0] if c[0] else c[1].get("text", "") for c in calls]
    assert "You are safe" in last_text
    assert not any("NOT confirmed" in t for t in all_texts)
    assert_contract_invariants(msg, report)


@pytest.mark.asyncio
async def test_panic_null_cursor_ends_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    """G2: Cursor with value None ends pagination."""
    tracker = CallTracker()
    page1 = {
        "items": [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(5)],
        "cursor": None,
    }
    client = make_mock_client(tracker, list_responses=[page1])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert len(client._list_calls) == 1
    assert len(client._delete_calls) == 1
    assert client._delete_calls[0]["kwargs"]["offer_ids"] == [f"o{i}" for i in range(5)]
    report = parse_report(msg)
    assert report["confirmed"] == 5
    assert report["list_complete"] == "yes"
    assert_contract_invariants(msg, report)
    assert_verdict(msg, report, expected_safe=True)
@pytest.mark.asyncio
async def test_panic_report_scope_matches_game_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """S1: Panic report includes 'scope: <GAME_ID>' matching first positional arg of get_user_offers_v2."""
    tracker = CallTracker()
    items = [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(3)]
    client = make_mock_client(tracker, list_responses=[{"items": items}])
    state = make_state(client=client, tracker=tracker)
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert len(client._list_calls) == 1
    call_arg = client._list_calls[0]["args"][0]
    assert call_arg == "test-game"

    report = parse_report(msg)
    if "scope" not in report:
        scope_match = re.search(r"(?m)^\s*scope:\s*(.+)$", report["_text"])
        report["scope"] = scope_match.group(1).strip() if scope_match else None

    assert report["scope"] == "test-game"
    assert report["scope"] == call_arg
    assert report["confirmed"] == 3
    assert report["list_complete"] == "yes"
    assert report["stop_ok"] == "yes"

    assert_verdict(msg, report, expected_safe=True)
    assert_contract_invariants(msg, report)
@pytest.mark.asyncio
async def test_panic_holds_state_lock_during_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    """L1: state.lock is held during all list and delete API calls in _cancel_all_offers."""
    tracker = CallTracker()
    lock_records: list[bool] = []

    state = make_state(client=None, tracker=tracker)
    if not isinstance(state.lock, asyncio.Lock):
        state.lock = asyncio.Lock()

    items = [{"offerId": f"o{i}", "attributes": {"id": f"A{i}"}} for i in range(3)]

    def mock_list(*args: Any, **kwargs: Any) -> dict[str, Any]:
        lock_records.append(state.lock.locked())
        return {"items": items}

    def mock_batch(*args: Any, offer_ids: list[str] | None = None, **kwargs: Any) -> dict[str, Any]:
        lock_records.append(state.lock.locked())
        ids = offer_ids or []
        return {"offers": [{"id": oid} for oid in ids]}

    client = make_mock_client(
        tracker,
        list_responses=mock_list,
        batch_responses=mock_batch,
    )
    state.client = client
    monkeypatch.setattr("src.telegram.control_bot.commands.control.state", state)

    msg = make_message()
    await cmd_panic(msg)

    assert len(client._list_calls) >= 1
    assert len(client._delete_calls) >= 1
    assert all(lock_records)
    assert not state.lock.locked()


