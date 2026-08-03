# WEAPON_DIVERSITY_REPORT.md — Анализ ликвидности оружия вне AK-47
## Date: 2026-08-01 | Balance: $43.91 | READ-ONLY (не коммитить)

---

## Категория: Pistols

| Title | Bid | Ask | BC | AC | Spread | Q | Score | Status |
|-------|-----|-----|----|----|--------|---|-------|--------|
| Five-SeveN \| Angry Mob (BS) | $49.78 | $52.09 | 129 | 8 | 4.4% | 16.1 | 2455 | PASS |
| R8 Revolver \| Skull Crusher (FT) | $6.70 | $7.35 | 310 | 66 | 8.8% | 4.7 | 922 | PASS |
| Desert Eagle \| Sputnik (FT) | $1.78 | $2.16 | 299 | 60 | 17.6% | 5.0 | 495 | PASS |
| CZ75-Auto \| Circaetus (WW) | $0.15 | $0.17 | 160 | 25 | 11.8% | 6.4 | 421 | PASS |
| Glock-18 \| Off World (WW) ST | $0.35 | $0.45 | 165 | 93 | 22.2% | — | 0 | FAIL: spread >20% |
| Glock-18 \| Candy Apple (FN) | $2.45 | $2.50 | 93 | 954 | 2.0% | — | 0 | FAIL: Q=0.1 < 2.0x |
| ST Desert Eagle \| Corinthian (MW) | $1.92 | $2.12 | 69 | 110 | 9.4% | — | 0 | FAIL: Q=0.6 < 2.0x |

**26 items total, 4 passed demand gate. Median score: 922.**

---

## Категория: SMGs

| Title | Bid | Ask | BC | AC | Spread | Q | Score | Status |
|-------|-----|-----|----|----|--------|---|-------|--------|
| MAC-10 \| Saibā Oni (FT) | $0.93 | $0.97 | 233 | 108 | 4.1% | 2.2 | 176 | PASS |
| ST MAC-10 \| Sakkaku (BS) | $0.40 | $0.43 | 144 | 69 | 7.0% | 2.1 | 103 | PASS |
| ST MAC-10 \| Ensnared (FT) | $0.12 | $0.16 | 281 | 260 | 25.0% | — | 0 | FAIL: spread >20% |
| ST MP9 \| Featherweight (FT) | $0.11 | $0.17 | 5 | 422 | 35.3% | — | 0 | FAIL: spread >20% |

**18 items total, 2 passed. Median score: 176.**

---

## Категория: Rifles (non-AK)

| Title | Bid | Ask | BC | AC | Spread | Q | Score | Status |
|-------|-----|-----|----|----|--------|---|-------|--------|
| M4A1-S \| Liquidation (MW) | $4.54 | $5.43 | 339 | 58 | 16.4% | 5.8 | 753 | PASS |
| Galil AR \| Firefight (FT) | $1.00 | $1.19 | 371 | 101 | 16.0% | 3.7 | 354 | PASS |
| ST M4A1-S \| Night Terror (FN) | $4.17 | $4.57 | 397 | 181 | 8.8% | 2.2 | 309 | PASS |
| M4A4 \| Converter (FN) | $2.07 | $2.59 | 273 | 218 | 20.1% | — | 0 | FAIL: spread >20% |
| M4A1-S \| Black Lotus (FT) | $6.36 | $6.78 | 240 | 1366 | 6.2% | — | 0 | FAIL: Q=0.2 < 2.5x |

**18 items total, 3 passed. Median score: 354.**

---

## Категория: Snipers

| Title | Bid | Ask | BC | AC | Spread | Q | Score | Status |
|-------|-----|-----|----|----|--------|---|-------|--------|
| ST AWP \| Exoskeleton (MW) | $12.99 | $13.47 | 305 | 31 | 3.6% | 9.8 | 3614 | PASS |
| G3SG1 \| Ventilator (WW) | $0.17 | $0.21 | 147 | 7 | 19.0% | 21.0 | 1797 | PASS |
| AWP \| Black Nile (FN) | $29.18 | $31.47 | 100 | 33 | 7.3% | 3.0 | 136 | PASS |
| SSG 08 \| Spring Twilly (FN) | $6.72 | $8.02 | 153 | 85 | 16.2% | — | 0 | FAIL: Q=1.8 < 2.5x |
| ST SSG 08 \| Dezastre (WW) | $0.04 | $0.12 | 105 | 410 | 66.7% | — | 0 | FAIL: spread >20% |

**12 items total, 3 passed. Median score: 1797.**

---

## Категория: Heavy

| Title | Bid | Ask | BC | AC | Spread | Q | Score | Status |
|-------|-----|-----|----|----|--------|---|-------|--------|
| Sawed-Off \| Limelight (FN) | $6.70 | $8.19 | 213 | 4 | 18.2% | 53.2 | 6420 | PASS |
| ST XM1014 \| Oxide Blaze (MW) | $0.15 | $0.18 | 123 | 27 | 16.7% | 4.6 | 173 | PASS |
| Souvenir Nova \| Army Sheen (MW) | $0.18 | $0.25 | 213 | 220 | 28.0% | — | 0 | FAIL: spread >20% |
| XM1014 \| Slipstream (FT) | $0.19 | $0.42 | 479 | 101 | 54.8% | — | 0 | FAIL: spread >20% |

**18 items total, 2 passed. Median score: 6420.**

---

## Summary

| Категория | Total | Passed | Median Score | Top Passer |
|-----------|-------|--------|-------------|------------|
| Pistols | 26 | 4 | 922 | Five-SeveN Angry Mob ($52, Q=16) |
| SMGs | 18 | 2 | 176 | MAC-10 Saibā Oni ($0.97, Q=2.2) |
| Rifles | 18 | 3 | 354 | M4A1-S Liquidation ($5.43, Q=5.8) |
| Snipers | 12 | **3** | **1797** | **ST AWP Exoskeleton ($13.47, Q=9.8)** |
| Heavy | 18 | **2** | **6420** | **Sawed-Off Limelight ($8.19, Q=53.2)** |
| AK-47 | 92 | ~14 | ~2000 | AK-47 Baroque Purple ($6.13, Q=34) |

### Top-10 non-AK-47 candidates (by score)

| # | Title | Price | Q | OBI | Score | Cat |
|---|-------|-------|---|-----|-------|-----|
| 1 | Sawed-Off \| Limelight (FN) | $8.19 | 53.2 | +0.96 | 6420 | Heavy |
| 2 | ST AWP \| Exoskeleton (MW) | $13.47 | 9.8 | +0.82 | 3614 | Snipers |
| 3 | Five-SeveN \| Angry Mob (BS) | $52.09 | 16.1 | +0.88 | 2455 | Pistols |
| 4 | G3SG1 \| Ventilator (WW) | $0.21 | 21.0 | +0.91 | 1797 | Snipers |
| 5 | R8 Revolver \| Skull Crusher (FT) | $7.35 | 4.7 | +0.65 | 922 | Pistols |
| 6 | M4A1-S \| Liquidation (MW) | $5.43 | 5.8 | +0.71 | 753 | Rifles |
| 7 | Desert Eagle \| Sputnik (FT) | $2.16 | 5.0 | +0.67 | 495 | Pistols |
| 8 | CZ75-Auto \| Circaetus (WW) | $0.17 | 6.4 | +0.73 | 421 | Pistols |
| 9 | Galil AR \| Firefight (FT) | $1.19 | 3.7 | +0.58 | 354 | Rifles |
| 10 | ST M4A1-S \| Night Terror (FN) | $4.57 | 2.2 | +0.38 | 309 | Rifles |

---

## Анализ: системный перекос против дешёвых предметов

### Spread entropy — главный фильтр-убийца

**72% отклонённых предметов** отсеиваются по "spread too wide (>20%)". Это НЕ баг фильтра — это рыночная реальность: дешёвые предметы (<$1) имеют spreads 20-90% из-за низкой ликвидности.

### Дешёвые предметы: проблема абсолютных count

| Предмет | Price | BC | AC | Q | Spread | Status |
|---------|-------|----|----|---|--------|--------|
| CZ75 Circaetus (WW) | $0.17 | 160 | 25 | 6.4 | 11.8% | **PASS** |
| XM1014 Slipstream (FT) | $0.42 | 479 | 101 | 4.7 | 54.8% | **FAIL: spread** |
| MP9 Featherweight (BS) | $0.09 | 383 | 210 | 1.8 | 55.6% | **FAIL: spread** |

Проблема: даже при высоком Q (6.4), если spread > 20%, предмет отсеивается. Для дешёвых предметов spread почти всегда > 20% — это природный закон рынка (wide tick size relative to price).

### Рекомендация (не менять сейчас)

**Spread entropy filter корректен для AK-47 ($2-$15), но системно дискриминирует предметы <$1.** Для будущих итераций рассмотреть:
- Адаптивный spread threshold: <$1 → 40%, $1-$5 → 25%, >$5 → 20%
- Или полностью отключить spread filter для предметов с Q > 5x (высокий спрос компенсирует широкий spread)

**Это не блокирует запуск** — бот и так находит14+ кандидатов из AK-47 сегмента. Но для диверсификации портфеля — worth considering.
