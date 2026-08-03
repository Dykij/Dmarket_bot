# WEAR_MATRIX_REPORT.md — Полная wear-матрица топ-10 не-AK кандидатов
## Date: 2026-08-01 | READ-ONLY (не коммитить)

---

## Финальный топ-10 (все wear-состояния)

| # | Title | Ask | Q | Spread | Score |
|---|-------|-----|---|--------|-------|
| 1 | **R8 Revolver \| Skull Crusher (BS)** | $5.05 | **39.7** | 7.3% | **12576** |
| 2 | **Sawed-Off \| Limelight (WW)** | $1.03 | **41.6** | 2.9% | **9845** |
| 3 | R8 Revolver \| Skull Crusher (WW) | $5.11 | 28.5 | 5.1% | 9342 |
| 4 | Sawed-Off \| Limelight (FN) | $8.18 | 53.2 | 18.1% | 6420 |
| 5 | Five-SeveN \| Angry Mob (WW) | $52.99 | 39.0 | 4.5% | 5200 |
| 6 | Five-SeveN \| Angry Mob (FT) | $52.19 | 21.7 | 2.8% | 4911 |
| 7 | Five-SeveN \| Angry Mob (MW) | $56.96 | 15.8 | 4.6% | 2647 |
| 8 | G3SG1 \| Ventilator (FN) | $0.71 | 20.2 | 14.1% | 2612 |
| 9 | AWP \| Exoskeleton (BS) | $4.12 | 12.1 | 11.7% | 2541 |
| 10 | Five-SeveN \| Angry Mob (BS) | $52.08 | 16.1 | 4.4% | 2455 |

---

## Ключевое открытие: wear-состояние критично

### Sawed-Off | Limelight

| Wear | Ask | BC | AC | Q | Spread | Score | Status |
|------|-----|----|----|---|--------|-------|--------|
| **Well-Worn** | **$1.03** | **208** | **5** | **41.6** | **2.9%** | **9845** | **PASS** |
| Factory New | $8.18 | 213 | 4 | 53.2 | 18.1% | 6420 | PASS |
| Minimal Wear | $2.57 | 209 | 14 | — | 30.4% | 0 | FAIL: spread |
| Field-Tested | $1.33 | 326 | 19 | — | 22.6% | 0 | FAIL: spread |
| Battle-Scarred | $1.47 | 317 | 2 | — | 36.7% | 0 | FAIL: spread |

**WW > FN** — несмотря на более низкий Q (41.6 vs53.2), WW имеет spread 2.9% vs 18.1%. Score9845 vs 6420.

### R8 Revolver | Skull Crusher

| Wear | Ask | BC | AC | Q | Spread | Score | Status |
|------|-----|----|----|---|--------|-------|--------|
| **Battle-Scarred** | **$5.05** | **278** | **7** | **39.7** | **7.3%** | **12576** | **PASS** |
| Well-Worn | $5.11 | 285 | 10 | 28.5 | 5.1% | 9342 | PASS |
| Field-Tested | $7.35 | 310 | 66 | 4.7 | 8.7% | 922 | PASS |

**BS > WW > FT** — BS имеет Q=39.7 (278 buyers, 7 sellers). Невероятный дисбаланс.

### AWP | Exoskeleton

| Wear | Ask | BC | AC | Q | Spread | Score | Status |
|------|-----|----|----|---|--------|-------|--------|
| **Battle-Scarred** | **$4.12** | **350** | **29** | **12.1** | **11.7%** | **2541** | **PASS** |
| Well-Worn | $4.10 | 423 | 68 | 6.2 | 6.3% | 2111 | PASS |
| Factory New | $51.14 | 242 | 25 | 9.7 | 18.0% | 1390 | PASS |
| Minimal Wear | $10.74 | 330 | 60 | 5.5 | 2.8% | 1311 | PASS |
| Field-Tested | $5.11 | 521 | 89 | 5.9 | 10.6% | 1161 | PASS |

**BS > WW > FN** — все5 wear-состояния PASS! FN стоит $51 — вне бюджета.

---

## Топ-2: Sawed-Off WW и ST AWP BS — подтверждены?

| # | Skin | Best Wear | Ask | Q | Score | Verdict |
|---|------|-----------|-----|---|-------|---------|
| 1 | R8 Skull Crusher | **BS** | $5.05 | 39.7 | **12576** | **НОВЫЙ #1!** |
| 2 | Sawed-Off Limelight | **WW** | $1.03 | 41.6 | **9845** | **ПОДТВЕРЖДЁН** (FN был хуже) |
| 3 | AWP Exoskeleton | **BS** | $4.12 | 12.1 | **2541** | **НОВЫЙ #3!** (FN был хуже)

**R8 Skull Crusher BS — абсолютный лидер** с score=12576. Sawed-Off WW подтверждён как #2. AWP BS обгоняет FN.

---

## Системный insight: wear-состояние меняет всё

**5 из 10 лучших кандидатов** — это НЕ тот wear, который был в исходном WEAPON_DIVERSITY_REPORT.md. Полный wear-matrix выявил:
- R8 BS (score=12576) >> R8 FT (score=922) — **14x лучше!**
- Sawed-Off WW (score=9845) >> Sawed-Off FN (score=6420) — **1.5x лучше**
- AWP BS (score=2541) >> AWP FN (score=1390) — **1.8x лучше**

**Всегда проверять все5 wear-состояний, не только один.**
