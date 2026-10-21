# Liquidity Dashboard

An interactive Streamlit application that computes the **Liquidity Coverage Ratio (LCR)**, the **Net Stable Funding Ratio (NSFR)** and the **survival horizon under stress** of a bank. Inputs are the bank's balance sheet broken down by category and residual maturity.

* **Regulatory parameters** follow the Basel Committee standards (LCR 2013 and NSFR 2014, consolidated in **LIQ30** and **LIQ40**).
* **EU switch**: Delegated Regulation (EU) **2015/61** for the LCR and **CRR Articles 428a-428az** for the NSFR.

**Live app:** `https://<your-app-name>.streamlit.app` *(to be completed after deployment)*

![tests](https://github.com/ldenarbonne/liquidity-dashboard/actions/workflows/tests.yml/badge.svg)

---

## 1. Features

| Tab | Content |
|---|---|
| **Overview** | LCR, NSFR and survival horizons, liquidity surplus under the three scenarios, BCBS vs EU comparison |
| **LCR** | HQLA by level with haircuts and 15% / 40% caps (EU: 70% cap on Level 1 covered bonds), 30-day outflows and inflows, 75% inflow cap, waterfall chart |
| **NSFR** | ASF and RSF by category and maturity bucket, derivative add-ons, charts by source and use |
| **Survival horizon** | 90-day daily ladder under idiosyncratic, market-wide and combined stress, counterbalancing capacity, outflows by source, CSV export |
| **Methodology** | Formulas, EU deviations, limitations |

**Inputs** come from two sources:
* a demo bank (EUR 50 bn balance sheet) that can be edited row by row;
* a CSV file (`code, d30, m6, m12, y1`).

A pre-filled template and a reference table of the 41 categories, with their treatments in both regimes, are in `templates/`. The stress assumptions (run-off, rollover and draw-down rates, haircuts, monetisation lags, central bank access) can be edited in the app.

## 2. EU deviations implemented

| Item | BCBS | EU |
|---|---|---|
| Extremely high-quality covered bonds | Level 2A, 15% haircut, RSF 15% | Level 1, 7% haircut, 70% cap, RSF 7% |
| Non-RMBS securitisations | not HQLA | Level 2B, 35% haircut, RSF 35% |
| Level 2B RMBS – RSF | 50% | 25% |
| Reverse repos with financials < 6m, Level 1 collateral | RSF 10% | RSF 0% |
| Reverse repos with financials < 6m, other collateral | RSF 15% | RSF 5% |
| Unsecured loans to financials < 6m | RSF 15% | RSF 10% |
| Cover-pool assets encumbered for covered bonds | RSF 100% | RSF 85% |
| Gross derivative liabilities | RSF 20% | RSF 5% |
| Operational deposits held at other banks (LCR inflow) | 0% | 5% |
| Inflow cap | 75% | 75% (90% for specialised institutions with approval) |

The deviations are documented in the BCBS RCAP assessments of the EU (LCR 2017, NSFR 2022). The reduced RSF factors for short-term transactions with financial customers were kept in 2025.

## 3. Illustrative results (demo bank, EUR m)

| | BCBS | EU |
|---|---|---|
| Stock of HQLA | 10,150 | 10,465 |
| Net cash outflows | 6,565 | 6,550 |
| **LCR** | **154.6%** | **159.8%** |
| Available stable funding | 37,285 | 37,285 |
| Required stable funding | 27,072 | 25,677 |
| **NSFR** | **137.7%** | **145.2%** |

| Scenario | Survival horizon | Minimum surplus over 90 days |
|---|---|---|
| Idiosyncratic | 85 days | −461 |
| Market-wide | > 90 days | +1,951 |
| Combined | 71 days | −2,358 |

Both regulatory ratios are comfortable. Even so, under the combined scenario the bank runs out of liquidity before 90 days. This is the gap the survival horizon is designed to reveal: the LCR only covers 30 days and assumes stylised outflows.

## 4. Project structure

```
liquidity-dashboard/
├── app.py                 # Streamlit front-end
├── liquidity/
│   ├── params.py          # Category catalogue: LCR, NSFR and stress treatments by regime
│   ├── ratios.py          # LCR (HQLA caps, inflow cap) and NSFR (ASF / RSF, derivatives)
│   ├── stress.py          # 90-day survival horizon with counterbalancing capacity
│   ├── io.py              # CSV import, validation, scenario tables
│   └── demo.py            # Demo balance sheet and derivative inputs
├── templates/             # Balance-sheet template and category reference
├── tests/                 # 18 pytest tests (hand-checked caps, ratios, survival horizon, app)
└── .github/workflows/     # CI on Python 3.11 and 3.12
```

## 5. Run locally

```bash
git clone https://github.com/ldenarbonne/liquidity-dashboard.git
cd liquidity-dashboard
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q
streamlit run app.py
```

## 6. Deploy on Streamlit Community Cloud

1. Push the repository to GitHub (public).
2. On [share.streamlit.io](https://share.streamlit.io), click **Create app**, choose the repository, branch `main` and main file `app.py`; select Python 3.12.
3. Paste the app URL at the top of this README.

## 7. Limitations

* The balance sheet is entered by category and maturity bucket, not contract by contract; flows are spread uniformly within each bucket.
* Adjusted HQLA amounts only unwind repos secured by Level 2A collateral. Collateral received in reverse repos is not counted in HQLA.
* The EU 70% cap is implemented in a simplified form. Other EU specificities (CIUs, cooperative networks, credit unions) are not modelled.
* Stress assumptions are illustrative and should be calibrated within an ILAAP.
* Educational tool: it does not replace regulatory reporting.

## 8. References

* BCBS (2013), *Basel III: The Liquidity Coverage Ratio and liquidity risk monitoring tools*; BCBS (2014), *Basel III: The Net Stable Funding Ratio*; Basel Framework LIQ30 and LIQ40.
* Commission Delegated Regulation (EU) 2015/61 (LCR); Regulation (EU) No 575/2013, Part Six (NSFR).
* BCBS, *RCAP – Assessment of Basel III LCR regulations – European Union* (July 2017) and *RCAP – Assessment of the NSFR standard – European Union* (July 2022).

---

**Author:** [Laurent Motais de Narbonne](https://www.linkedin.com/in/laurent-motais-de-narbonne/), Senior Risk Manager. MIT licence.
