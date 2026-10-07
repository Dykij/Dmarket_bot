#!/usr/bin/env python3
"""obi_collector: снимки aggregated-prices по ФИКСИРОВАННОМУ списку названий раз в INTERVAL секунд.

Пишет (в --out-dir, файлы текущего запуска с меткой TAG):
  snap_<TAG>.csv   tick_ts, recv_ts, name, best_ask, best_bid, ask_count, bid_count (одна строка = название в узле сетки)
  ticks_<TAG>.csv  tick_ts, start_ts, dur_s, expected, returned, chunks_ok, chunks_failed, status, error
  run_<TAG>.json   метаданные запуска: версия, коммит, sha256 списка, интервал, время начала/конца, код выхода

Узлы сетки кратны INTERVAL по часам (UTC epoch), поэтому каденс фиксирован; опоздавшие узлы пропускаются и
помечаются в ticks (status=skipped). SIGTERM/SIGINT: дописать и выйти с кодом 0.
Коды выхода: 0 штатно, 2 ошибка авторизации (401/403), 3 слишком много пустых тиков подряд, 4 ошибка запуска.
Запросы: только POST /marketplace-api/v1/aggregated-prices (чтение). Ключи не печатаются и не пишутся.
Режимы: обычный запуск, --selftest (без сети и без бота).
"""

import argparse
import asyncio
import csv
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

VERSION = "1.1"
REPO = Path(
    os.environ.get("DMARKET_REPO") or Path(__file__).resolve().parents[2]
)  # корень репозитория
CHUNK = 100
MAX_EMPTY_TICKS = 12  # подряд пустых тиков до выхода с кодом 3 (при 5 минутах это час)
SNAP_HEADER = ["tick_ts", "recv_ts", "name", "best_ask", "best_bid", "ask_count", "bid_count"]
TICK_HEADER = [
    "tick_ts",
    "start_ts",
    "dur_s",
    "expected",
    "returned",
    "chunks_ok",
    "chunks_failed",
    "status",
    "error",
]


def read_titles(path):
    raw = Path(path).read_bytes()
    seen, titles = set(), []
    for line in raw.decode("utf-8").splitlines():
        t = line.strip()
        if not t or t.startswith("#") or t in seen:
            continue
        seen.add(t)
        titles.append(t)
    return titles, hashlib.sha256(raw).hexdigest()


def chunked(seq, n):
    return [seq[i : i + n] for i in range(0, len(seq), n)]


def _num(x):
    return int(x) if float(x).is_integer() else round(float(x), 3)


async def fetch_tick(fetch_chunk, parse, titles):
    entries, ok, failed, err, fatal = [], 0, 0, "", False
    for ch in chunked(titles, CHUNK):
        try:
            entries.extend(parse(await fetch_chunk(ch)))
            ok += 1
        except Exception as e:  # noqa: BLE001 - любой сбой чанка не должен ронять сбор
            failed += 1
            err = f"{type(e).__name__}: {str(e)[:120]}"
            if getattr(e, "status", None) in (401, 403):
                fatal = True
    return {"entries": entries, "ok": ok, "failed": failed, "err": err, "fatal": fatal}


async def wait_until(t, stop, now):
    while not stop.is_set():
        d = t - now()
        if d <= 0:
            return True
        try:
            await asyncio.wait_for(stop.wait(), timeout=min(d, 1.0))
        except asyncio.TimeoutError:
            pass
    return False


def _git_commit():
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha
    try:
        return (
            subprocess.run(
                ["git", "-C", str(REPO), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            or "unknown"
        )
    except Exception:  # noqa: BLE001
        return "unknown"


def _write_json(path, data):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


async def run(
    fetch_chunk,
    parse,
    titles,
    titles_sha,
    out_dir,
    tag,
    interval,
    duration,
    max_ticks,
    stop,
    now=time.time,
    max_empty=MAX_EMPTY_TICKS,
    log=print,
):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    snap_p, tick_p, meta_p = (
        out_dir / f"snap_{tag}.csv",
        out_dir / f"ticks_{tag}.csv",
        out_dir / f"run_{tag}.json",
    )
    t0 = now()
    meta = {
        "version": VERSION,
        "tag": tag,
        "run_id": os.environ.get("GITHUB_RUN_ID", tag),
        "commit": _git_commit(),
        "n_titles": len(titles),
        "titles_sha256": titles_sha,
        "interval_s": interval,
        "duration_s": duration,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "start_utc": datetime.fromtimestamp(t0, timezone.utc).isoformat(),
        "end_utc": None,
        "ticks": 0,
        "rows": 0,
        "exit_code": None,
    }
    _write_json(meta_p, meta)
    deadline = t0 + duration if duration else None
    next_tick = (int(t0 // interval) + 1) * interval
    n_ticks = rows = empty_streak = code = 0
    with (
        open(snap_p, "w", newline="", encoding="utf-8") as sf,
        open(tick_p, "w", newline="", encoding="utf-8") as tf,
    ):
        sw, tw = csv.writer(sf), csv.writer(tf)
        sw.writerow(SNAP_HEADER)
        tw.writerow(TICK_HEADER)
        while True:
            if max_ticks and n_ticks >= max_ticks:
                break
            if deadline and next_tick > deadline:
                break
            if not await wait_until(next_tick, stop, now):
                break
            start = now()
            res = await fetch_tick(fetch_chunk, parse, titles)
            dur = now() - start
            returned = len(res["entries"])
            for e in res["entries"]:
                sw.writerow(
                    [
                        _num(next_tick),
                        round(start, 3),
                        e["title"],
                        e["best_ask"],
                        e["best_bid"],
                        e["ask_count"],
                        e["bid_count"],
                    ]
                )
            sf.flush()
            rows += returned
            status = (
                "ok"
                if res["failed"] == 0 and returned > 0
                else ("partial" if returned > 0 else "fail")
            )
            tw.writerow(
                [
                    _num(next_tick),
                    round(start, 3),
                    round(dur, 2),
                    len(titles),
                    returned,
                    res["ok"],
                    res["failed"],
                    status,
                    res["err"],
                ]
            )
            tf.flush()
            n_ticks += 1
            log(f"tick {_num(next_tick)} {status} {returned}/{len(titles)} {dur:.1f}s")
            empty_streak = empty_streak + 1 if returned == 0 else 0
            if res["fatal"]:
                code = 2
                break
            if empty_streak >= max_empty:
                code = 3
                break
            next_tick += interval
            t = now()
            if t > next_tick:  # опоздали: пропускаем узлы, чтобы сетка не поплыла
                skipped = int((t - next_tick) // interval) + 1
                tw.writerow(
                    [
                        _num(next_tick),
                        round(t, 3),
                        0,
                        len(titles),
                        0,
                        0,
                        0,
                        "skipped",
                        f"{skipped} узл.",
                    ]
                )
                tf.flush()
                next_tick += skipped * interval
    meta.update(
        {
            "end_utc": datetime.fromtimestamp(now(), timezone.utc).isoformat(),
            "ticks": n_ticks,
            "rows": rows,
            "exit_code": code,
        }
    )
    _write_json(meta_p, meta)
    return code


def make_real_fetcher():
    """Ключи берутся из окружения (Actions) или из .env репозитория (локально) ДО импорта бота."""
    tmp = tempfile.TemporaryDirectory(prefix="obi_collector_data_")
    os.environ["DMARKET_DATA_DIR"] = tmp.name  # бот не должен писать в data/ репозитория
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    if not (os.environ.get("DMARKET_PUBLIC_KEY") and os.environ.get("DMARKET_SECRET_KEY")):
        env = REPO / ".env"
        if env.is_file():
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=str(env), override=False)
    pub = os.environ.get("DMARKET_PUBLIC_KEY", "").strip()
    sec = os.environ.get("DMARKET_SECRET_KEY", "").strip()
    if not pub or not sec or pub.startswith("ROTATE_ME"):
        sys.exit("СТОП: ключи не настроены (значения не печатаю)")
    os.chdir(REPO)
    sys.path.insert(0, str(REPO))
    from src.api.dmarket_api_client.core import DMarketAPIClient
    from src.api.dmarket_parser import parse_aggregated_prices_from_dict
    from src.config import Config

    client = DMarketAPIClient(public_key=pub, secret_key=sec)
    game_id = getattr(Config, "GAME_ID", "a8db")

    async def fetch_chunk(ch):
        return await client.make_request(
            "POST",
            "/marketplace-api/v1/aggregated-prices",
            body={"limit": 100, "filter": {"game": game_id, "titles": ch}},
        )

    return client, fetch_chunk, parse_aggregated_prices_from_dict, tmp


async def amain(a):
    titles, sha = read_titles(a.titles)
    if not titles:
        sys.exit("СТОП: пустой список названий")
    tag = a.label or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    client, fetch_chunk, parse, tmp = make_real_fetcher()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for s in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(s, stop.set)
    print(f"сбор: {len(titles)} названий, интервал {a.interval}s, тег {tag}, sha списка {sha[:12]}")
    try:
        return await run(
            fetch_chunk,
            parse,
            titles,
            sha,
            a.out_dir,
            tag,
            a.interval,
            a.duration_sec,
            a.max_ticks,
            stop,
        )
    finally:
        await client.close()
        tmp.cleanup()


# ----------------------------------------------------------------------------- selftest (без сети и без бота)
class _Err(Exception):
    def __init__(self, status=None):
        super().__init__(f"fake error {status}")
        self.status = status


def selftest():
    import shutil

    base = Path(tempfile.mkdtemp(prefix="obi_selftest_"))
    names = [f"AK-47 | T{i} (Field-Tested)" for i in range(250)]  # 3 пачки: 100+100+50

    def mk_fetch(fail_chunks=(), status=None, on_call=None):
        calls = {"n": 0}

        async def fetch(ch):
            calls["n"] += 1
            if on_call:
                on_call(calls["n"])
            idx = names.index(ch[0]) // CHUNK
            if idx in fail_chunks:
                raise _Err(status)
            return {
                "e": [
                    {"title": n, "best_ask": 1.5, "best_bid": 1.4, "ask_count": 5, "bid_count": 6}
                    for n in ch
                ]
            }

        return fetch, calls

    parse = lambda raw: raw["e"]  # noqa: E731
    quiet = lambda *_: None  # noqa: E731

    def rd(p):
        return list(csv.reader(open(p, encoding="utf-8")))

    def go(tag, fetch, **kw):
        stop = kw.pop("stop", asyncio.Event())
        args = dict(interval=0.3, duration=0, max_ticks=3)
        args.update(kw)
        code = asyncio.run(run(fetch, parse, names, "sha", base, tag, stop=stop, log=quiet, **args))
        return (
            code,
            rd(base / f"snap_{tag}.csv"),
            rd(base / f"ticks_{tag}.csv"),
            json.loads((base / f"run_{tag}.json").read_text()),
        )

    # 1. нормальный ход: 3 тика, 250 строк на тик, сетка кратна интервалу
    f, calls = mk_fetch()
    code, snap, ticks, meta = go("t1", f)
    assert code == 0 and snap[0] == SNAP_HEADER and ticks[0] == TICK_HEADER
    assert len(snap) - 1 == 750 and len(ticks) - 1 == 3 and calls["n"] == 9, (
        len(snap),
        len(ticks),
        calls,
    )
    tt = [float(r[0]) for r in ticks[1:]]
    assert all(abs(x / 0.3 - round(x / 0.3)) < 1e-6 for x in tt), tt
    assert tt == sorted(tt) and len(set(tt)) == 3
    assert all(r[7] == "ok" for r in ticks[1:])
    assert (
        meta["ticks"] == 3
        and meta["rows"] == 750
        and meta["exit_code"] == 0
        and meta["n_titles"] == 250
    )
    assert meta["titles_sha256"] == "sha" and meta["end_utc"]
    # 2. частичный сбой чанка
    f, _ = mk_fetch(fail_chunks=(1,))
    code, snap, ticks, meta = go("t2", f)
    assert (
        code == 0
        and len(snap) - 1 == 450
        and all(r[7] == "partial" and r[6] == "1" for r in ticks[1:])
    ), ticks
    # 3. всё падает -> код 3 после max_empty тиков
    f, _ = mk_fetch(fail_chunks=(0, 1, 2))
    code, snap, ticks, meta = go("t3", f, max_empty=2, max_ticks=10)
    assert code == 3 and len(ticks) - 1 == 2 and meta["exit_code"] == 3, (code, ticks)
    # 4. 401 -> код 2 сразу
    f, _ = mk_fetch(fail_chunks=(0, 1, 2), status=401)
    code, snap, ticks, meta = go("t4", f, max_ticks=10)
    assert code == 2 and len(ticks) - 1 == 1, (code, ticks)
    # 5. остановка по сигналу в середине: файлы дописаны, код 0
    stop = asyncio.Event()
    f, calls = mk_fetch(on_call=lambda n: stop.set() if n == 4 else None)
    code, snap, ticks, meta = go("t5", f, stop=stop, max_ticks=10)
    assert code == 0 and meta["ticks"] == 2 and meta["end_utc"] and len(snap) - 1 == 500, (
        code,
        meta,
    )
    # 6. дедлайн: duration 1.0 при интервале 0.3 даёт не более 4 тиков и завершается сам
    f, _ = mk_fetch()
    code, snap, ticks, meta = go("t6", f, duration=1.0, max_ticks=0)
    assert code == 0 and 2 <= meta["ticks"] <= 4, meta

    # 7. опоздание: медленный клиент пропускает узлы сетки и помечает их
    async def slow(ch):
        await asyncio.sleep(0.5)
        return {
            "e": [
                {"title": n, "best_ask": 1, "best_bid": 1, "ask_count": 3, "bid_count": 3}
                for n in ch
            ]
        }

    code, snap, ticks, meta = go("t7", slow, interval=0.3, max_ticks=2)
    assert any(r[7] == "skipped" for r in ticks[1:]), ticks
    # 8. чтение списка: дубли, комментарии, sha
    tp = base / "titles.txt"
    tp.write_text(
        "# c\nA | B (Field-Tested)\n\nA | B (Field-Tested)\nC | D (Factory New)\n", encoding="utf-8"
    )
    ts, sh = read_titles(tp)
    assert (
        ts == ["A | B (Field-Tested)", "C | D (Factory New)"]
        and sh == hashlib.sha256(tp.read_bytes()).hexdigest()
    )
    shutil.rmtree(base, ignore_errors=True)
    print("selftest OK (8 проверок)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--titles", help="файл со списком названий (по одному в строке)")
    ap.add_argument("--out-dir", default=str(Path.home() / "dmarket_audits" / "collect"))
    ap.add_argument("--interval", type=float, default=300.0)
    ap.add_argument("--duration-sec", type=float, default=0.0, help="0 = без ограничения")
    ap.add_argument("--max-ticks", type=int, default=0, help="0 = без ограничения")
    ap.add_argument("--label", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    if not a.titles:
        sys.exit("нужен --titles")
    sys.exit(asyncio.run(amain(a)))


if __name__ == "__main__":
    main()
