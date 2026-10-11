#!/usr/bin/env python3
"""Проверка здоровья 6-недельного сбора OBI (только чтение, только stdlib).

Использование:
  python3 -I -B health_check.py <каталог_с_snapshots> [--quiet-if-ok] [--now ISO8601]
                                [--recent-hours H]

Что делает: читает run_*.json / ticks_*.csv.gz / snap_*.csv.gz из окна теста,
считает покрытие, дыры, возраст последнего тика, флаги запусков, качество
снимков и сверяет с ЗАРАНЕЕ заданными порогами (константы ниже).
Чего НЕ делает: не считает OBI/OFI и не смотрит доходность (чтобы не
подглядывать в тест до финального анализа).

Коды выхода: 0 — тревог нет; 1 — есть тревога; 2 — проверка не смогла отработать.
Любой нечитаемый/битый файл данных = тревога, а не молчаливый пропуск.

--recent-hours H: событийные тревоги (дыры, флаги запусков, ошибки тиков, chunks_failed,
строки без цены, повторы tick_ts) считаются только по запускам, закончившимся не раньше
H часов назад (запуск без end_utc считается свежим). Тревоги по состоянию (покрытие,
возраст тика, доля ask<bid) и накопительные цифры отчёта не меняются. Без параметра
проверяется вся история окна теста.
"""

import csv
import glob
import gzip
import json
import os
import sys
import time
from datetime import datetime, timezone

# ---- зафиксированные параметры теста (collect-v1) ----
WINDOW_START = datetime(2026, 10, 8, 12, 47, 54, tzinfo=timezone.utc)
MIN_RUN_ID = 37779348705
TEST_END = datetime(2026, 11, 19, tzinfo=timezone.utc)
CODE = "1e7e8daee0bfdee22b3097058fb83fd7a83e49ba"
TITLES = "980c94fead67eaf9ce8059b061afad6399ea55d602181d326003f05e87a2f523"
STEP = 300
EXPECTED_N = 300
TICKS_PER_RUN = 69

# ---- пороги тревоги (только для сообщений, к торговле не относятся) ----
MAX_GAP_MIN = 120  # дыра в данных дольше 2 ч
MAX_AGE_H = 8.0  # последний тик старше 8 ч (норма до ~6,6 ч между концами запусков)
MIN_COVERAGE_PCT = 90.0  # покрытие сетки ниже 90%
MAX_CROSSED_PCT = 5.0  # доля ask<bid выше 5% (на 2026-10-10 было 1,30%)
UNRELIABLE_BID_SHARE = 0.20  # правило проекта: >=20% снимков ask<bid -> «bid ненадёжен»


def rd(path):
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def fmt_ts(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%m-%d %H:%MZ")


def is_recent(m, now, recent_hours):
    if recent_hours is None:
        return True
    end = m.get("end_utc")
    if not end:
        return True
    try:
        return datetime.fromisoformat(end).timestamp() >= now - recent_hours * 3600
    except ValueError:
        return True


def main():
    args = sys.argv[1:]
    quiet_if_ok = "--quiet-if-ok" in args
    now = time.time()
    if "--now" in args:
        now = datetime.fromisoformat(args[args.index("--now") + 1]).timestamp()
    recent_hours = None
    if "--recent-hours" in args:
        try:
            recent_hours = float(args[args.index("--recent-hours") + 1])
        except (IndexError, ValueError):
            print("--recent-hours требует число часов", file=sys.stderr)
            return 2
    pos = [
        a
        for i, a in enumerate(args)
        if not a.startswith("--") and (i == 0 or args[i - 1] not in ("--now", "--recent-hours"))
    ]
    if not pos:
        print("нужен каталог с snapshots", file=sys.stderr)
        return 2
    root = pos[0]
    if not os.path.isdir(root):
        print(f"каталог не найден: {root}", file=sys.stderr)
        return 2

    alerts = []
    runs = []
    for jp in sorted(glob.glob(os.path.join(root, "**", "run_*.json"), recursive=True)):
        try:
            with open(jp, encoding="utf-8") as jf:
                m = json.load(jf)
            st = datetime.fromisoformat(m["start_utc"])
            if st < WINDOW_START or int(m["run_id"]) < MIN_RUN_ID:
                continue
            d, tag = os.path.dirname(jp), m["tag"]
            ticks = rd(os.path.join(d, f"ticks_{tag}.csv.gz"))
            snap = rd(os.path.join(d, f"snap_{tag}.csv.gz"))
        except Exception as e:  # битый/неполный файл = тревога
            alerts.append(f"не прочитан {os.path.basename(jp)}: {type(e).__name__}")
            continue
        runs.append((st, m, ticks, snap))
    runs.sort(key=lambda x: x[0])

    if not runs:
        print("нет запусков в окне теста — проверка не может отработать", file=sys.stderr)
        return 2

    all_ok = {}  # tick_ts -> run_id (тики ok 300/300)
    dup_ticks = 0
    status_ct, chunks_failed = {}, 0
    rows_total = crossed = zero = 0
    per_title = {}  # name -> [rows, crossed]
    run_lines, flagged = [], []
    recent_by_run = {}
    status_recent, chunks_recent, dup_recent, zero_recent = {}, 0, 0, 0

    for st, m, ticks, snap in runs:
        flags = []
        rec = is_recent(m, now, recent_hours)
        recent_by_run[m["run_id"]] = rec
        try:
            if m.get("commit") != CODE:
                flags.append("КОММИТ≠collect-v1")
            if m.get("titles_sha256") != TITLES:
                flags.append("СПИСОК≠frozen")
            if m.get("exit_code") != 0:
                flags.append(f"exit={m.get('exit_code')}")
            if m.get("end_utc") is None:
                flags.append("нет end_utc")
            if str(m.get("version")) != "1.2":
                flags.append(f"версия={m.get('version')}")
            ok_ticks = sum(1 for t in ticks if t["status"] == "ok")
            if len(snap) != ok_ticks * EXPECTED_N:
                flags.append("строк≠ok*300")
            if int(m.get("ticks", -1)) != TICKS_PER_RUN or len(ticks) != TICKS_PER_RUN:
                flags.append(f"тиков={m.get('ticks')}/{len(ticks)}≠{TICKS_PER_RUN}")
            for t in ticks:
                status_ct[t["status"]] = status_ct.get(t["status"], 0) + 1
                chunks_failed += int(t["chunks_failed"] or 0)
                if rec:
                    status_recent[t["status"]] = status_recent.get(t["status"], 0) + 1
                    chunks_recent += int(t["chunks_failed"] or 0)
                if t["status"] == "ok" and int(t["returned"]) == EXPECTED_N:
                    ts = int(t["tick_ts"])
                    if ts in all_ok:
                        dup_ticks += 1
                        dup_recent += int(rec)
                    all_ok[ts] = m["run_id"]
            for r in snap:
                rows_total += 1
                a, b = r["best_ask"], r["best_bid"]
                pt = per_title.setdefault(r["name"], [0, 0])
                pt[0] += 1
                if not a or not b or float(a) <= 0:
                    zero += 1
                    zero_recent += int(rec)
                elif float(a) < float(b):
                    crossed += 1
                    pt[1] += 1
        except Exception as e:
            flags.append(f"ошибка разбора {type(e).__name__}")
        end = (m.get("end_utc") or "-")[5:16].replace("T", " ")
        flag_txt = " ".join(flags) or "ok"
        run_lines.append(f"{m['run_id']} {st:%m-%d %H:%M}→{end} {m.get('ticks')}т {flag_txt}")
        if flags and rec:
            flagged.append((m["run_id"], flags))

    if not all_ok:
        print("нет ни одного тика ok 300/300", file=sys.stderr)
        return 2

    tss = sorted(all_ok)
    first, last = tss[0], tss[-1]
    expected = (last - first) // STEP + 1
    coverage = 100.0 * len(tss) / expected
    gaps = [(a, b, (b - a) // STEP - 1) for a, b in zip(tss, tss[1:], strict=False) if b - a > STEP]
    missed = sum(g[2] for g in gaps)
    max_gap = max(gaps, key=lambda g: g[2]) if gaps else None
    recent_gaps = [g for g in gaps if recent_by_run.get(all_ok[g[1]], True)]
    alert_gap = max(recent_gaps, key=lambda g: g[2]) if recent_gaps else None
    age_h = (now - last) / 3600
    crossed_pct = 100.0 * crossed / max(rows_total, 1)
    unreliable = sum(
        1 for rws, cr in per_title.values() if rws and cr / rws >= UNRELIABLE_BID_SHARE
    )
    all_files = glob.glob(os.path.join(root, "**", "*"), recursive=True)
    size_mb = sum(os.path.getsize(p) for p in all_files if os.path.isfile(p)) / 1e6

    # ---- проверка порогов ----
    for rid, fl in flagged:
        alerts.append(f"запуск {rid}: {', '.join(fl)}")
    bad = {k: v for k, v in status_recent.items() if k != "ok"}
    if bad:
        alerts.append(f"тики не ok: {bad}")
    if chunks_recent > 0:
        alerts.append(f"chunks_failed = {chunks_recent}")
    if dup_recent > 0:
        alerts.append(f"повторяющихся tick_ts между запусками: {dup_recent}")
    if alert_gap and alert_gap[2] * 5 > MAX_GAP_MIN:
        span = f"{fmt_ts(alert_gap[0])} → {fmt_ts(alert_gap[1])}"
        alerts.append(f"дыра {alert_gap[2] * 5} мин ({span}) > {MAX_GAP_MIN} мин")
    if age_h > MAX_AGE_H:
        alerts.append(
            f"последний тик {age_h:.1f} ч назад (> {MAX_AGE_H:g} ч), запуски могли остановиться"
        )
    if coverage < MIN_COVERAGE_PCT:
        alerts.append(f"покрытие {coverage:.2f}% < {MIN_COVERAGE_PCT:g}%")
    if zero_recent > 0:
        alerts.append(f"строк без цены/ask<=0: {zero_recent}")
    if crossed_pct > MAX_CROSSED_PCT:
        alerts.append(f"ask<bid {crossed_pct:.2f}% > {MAX_CROSSED_PCT:g}%")

    if quiet_if_ok and not alerts:
        return 0

    day = (datetime.fromtimestamp(now, timezone.utc) - WINDOW_START).days + 1
    total_days = (TEST_END - WINDOW_START).days
    out = []
    out.append("🔴 ТРЕВОГА сбора OBI" if alerts else "🟢 Сбор OBI в норме")
    out.append(
        f"день {day} из ~{total_days}; запусков {len(runs)}; "
        f"данные до {fmt_ts(last)} ({age_h:.1f} ч назад)"
    )
    if recent_hours is not None:
        out.append(f"Окно тревог: запуски, закончившиеся за последние {recent_hours:g} ч")
    if alerts:
        out.append("")
        out.append("Тревоги:")
        out.extend(f"• {a}" for a in alerts)
    out.append("")
    out.append(
        f"Покрытие: {len(tss)} из {expected} узлов = {coverage:.2f}%; "
        f"дыр {len(gaps)}, пропущено тиков {missed}"
    )
    if max_gap:
        span = f"{fmt_ts(max_gap[0])} → {fmt_ts(max_gap[1])}"
        out.append(f"Макс. дыра: {max_gap[2] * 5} мин ({span})")
    out.append(f"Тики: {status_ct}; chunks_failed {chunks_failed}")
    out.append(
        f"Качество: строк {rows_total}; ask<bid {crossed_pct:.2f}%; без цены {zero}; "
        f"названий с ≥20% ask<bid: {unreliable}/{len(per_title)}"
    )
    out.append(f"Размер данных: {size_mb:.2f} МБ")
    out.append("")
    out.append("Последние запуски:")
    out.extend(run_lines[-4:])
    print("\n".join(out))
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())
