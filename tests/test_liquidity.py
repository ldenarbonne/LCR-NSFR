"""Hand-checked LCR, NSFR and survival-horizon tests."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from liquidity import demo, ratios, stress
from liquidity import io as lio
from liquidity import params as P

BCBS, EU = P.regime("BCBS"), P.regime("EU")
NO_DER = P.Derivatives()


def bs(rows):
    df = pd.DataFrame(rows, columns=["code", "d30", "m6", "m12", "y1"])
    return lio.normalise(df)


# ---------------------------------------------------------------- HQLA caps

def test_no_cap_binding():
    s, a15, a40, a70 = ratios.hqla_stock(100, 0, 50, 10, {"L1": 100, "L1CB": 0, "L2A": 50, "L2B": 10}, BCBS)
    assert (s, a15, a40) == (160, 0.0, 0.0)


def test_15pct_cap_by_hand():
    # L1 = 100, L2A = 0, L2B = 50 -> adj15 = max(50 - 15/85*100, 50 - 15/60*100, 0) = 32.35
    s, a15, a40, _ = ratios.hqla_stock(100, 0, 0, 50, {"L1": 100, "L1CB": 0, "L2A": 0, "L2B": 50}, BCBS)
    assert a15 == pytest.approx(50 - 15 / 85 * 100)
    assert s / (100 + 50 - a15) == pytest.approx(1.0)
    assert (50 - a15) / s == pytest.approx(0.15)


def test_40pct_cap_by_hand():
    s, a15, a40, _ = ratios.hqla_stock(60, 0, 80, 0, {"L1": 60, "L1CB": 0, "L2A": 80, "L2B": 0}, BCBS)
    assert a40 == pytest.approx(80 - 2 / 3 * 60)
    assert (80 - a40) / s == pytest.approx(0.40)


def test_eu_70pct_cap_on_covered_bonds():
    s, _, _, a70 = ratios.hqla_stock(10, 100, 0, 0, {"L1": 10, "L1CB": 100, "L2A": 0, "L2B": 0}, EU)
    assert a70 == pytest.approx(100 - 7 / 3 * 10)
    assert (100 - a70) / s == pytest.approx(0.70)


# ---------------------------------------------------------------- LCR

def test_lcr_by_hand():
    b = bs([("A_CASH", 100, 0, 0, 0), ("A_L2A", 0, 0, 0, 40),
            ("L_RET_STABLE", 200, 50, 0, 0), ("L_FIN", 30, 0, 0, 0), ("O_CRED_NFC", 0, 0, 0, 100),
            ("A_LOAN_NFC", 20, 0, 0, 0)])
    r = ratios.compute_lcr(b, NO_DER, BCBS)
    hqla = 100 + 40 * 0.85
    out = 200 * 0.05 + 30 * 1.0 + 100 * 0.10      # term retail > 30 days: 0%
    inflow = 20 * 0.5
    assert r.hqla == pytest.approx(hqla)
    assert r.total_outflows == pytest.approx(out)
    assert r.ratio == pytest.approx(hqla / (out - inflow))


def test_inflow_cap():
    b = bs([("A_CASH", 10, 0, 0, 0), ("L_FIN", 100, 0, 0, 0), ("A_FIN_UNSEC", 200, 0, 0, 0)])
    r = ratios.compute_lcr(b, NO_DER, BCBS)
    assert r.capped_inflows == pytest.approx(75.0)
    assert r.ratio == pytest.approx(10 / 25)
    r_eu = ratios.compute_lcr(b, NO_DER, P.regime("EU", eu_specialised_inflow_cap=True))
    assert r_eu.capped_inflows == pytest.approx(90.0)


def test_retail_3pct_discretion():
    b = bs([("A_CASH", 10, 0, 0, 0), ("L_RET_STABLE", 100, 0, 0, 0)])
    assert ratios.compute_lcr(b, NO_DER, P.regime("BCBS", retail_stable_3pct=True)).total_outflows == pytest.approx(3.0)


def test_eu_covered_bonds_and_securitisations():
    b = bs([("A_CASH", 100, 0, 0, 0), ("A_L1_CB", 0, 0, 0, 100), ("A_L2B_SEC", 0, 0, 0, 20), ("L_FIN", 50, 0, 0, 0)])
    rb, re_ = ratios.compute_lcr(b, NO_DER, BCBS), ratios.compute_lcr(b, NO_DER, EU)
    assert rb.levels["L2A"] == pytest.approx(85.0) and rb.levels["L2B"] == 0.0
    assert re_.levels["L1CB"] == pytest.approx(93.0) and re_.levels["L2B"] == pytest.approx(13.0)


def test_derivative_outflows_included():
    der = P.Derivatives(net_outflows_30d=10, downgrade_collateral=5, hlba=7, net_inflows_30d=4)
    b = bs([("A_CASH", 100, 0, 0, 0)])
    r = ratios.compute_lcr(b, der, BCBS)
    assert r.total_outflows == pytest.approx(22.0) and r.total_inflows == pytest.approx(4.0)


# ---------------------------------------------------------------- NSFR

def test_nsfr_by_hand():
    b = bs([("L_CAPITAL", 0, 0, 0, 100), ("L_RET_STABLE", 300, 0, 0, 0), ("L_FIN", 50, 20, 30, 0),
            ("A_MORTGAGE", 10, 10, 10, 270), ("A_L1_SOV", 0, 0, 0, 100), ("A_REV_REPO_L1", 50, 0, 0, 0)])
    r = ratios.compute_nsfr(b, NO_DER, BCBS)
    asf = 100 + 300 * 0.95 + 70 * 0.0 + 30 * 0.5
    rsf = 20 * 0.5 + 10 * 0.5 + 270 * 0.65 + 100 * 0.05 + 50 * 0.10
    assert r.total_asf == pytest.approx(asf)
    assert r.total_rsf == pytest.approx(rsf)
    r_eu = ratios.compute_nsfr(b, NO_DER, EU)
    assert r_eu.total_rsf == pytest.approx(rsf - 50 * 0.10)       # 0% for L1-secured reverse repo


def test_nsfr_derivatives():
    der = P.Derivatives(nsfr_assets=100, nsfr_liabilities=40, gross_liabilities=200)
    b = bs([("L_CAPITAL", 0, 0, 0, 1000)])
    assert ratios.compute_nsfr(b, der, BCBS).total_rsf == pytest.approx(60 + 0.20 * 200)
    assert ratios.compute_nsfr(b, der, EU).total_rsf == pytest.approx(60 + 0.05 * 200)


# ---------------------------------------------------------------- stress

def test_hazard_matches_30_day_rate():
    x = stress._hazard(1000, 0.10)
    assert x[1:31].sum() == pytest.approx(100.0)


def test_survival_simple_case():
    # 320 of cash, 1,000 of financial deposits running off fully over 30 days (33.3 per day):
    # surplus 20 after day 9, deficit on day 10 -> survival horizon of 9 days
    b = bs([("A_CASH", 320, 0, 0, 0), ("L_FIN", 1000, 0, 0, 0)])
    sc = stress.default_scenarios()["Idiosyncratic"]
    sc.cb_access = False
    r = stress.run_stress(b, NO_DER, sc)
    assert r.survival_days == 9


def test_survival_more_than_90_days():
    b = bs([("A_CASH", 1000, 0, 0, 0), ("L_RET_STABLE", 100, 0, 0, 0)])
    r = stress.run_stress(b, NO_DER, stress.default_scenarios()["Market-wide"])
    assert r.survival_days == 91 and r.min_surplus > 0


def test_demo_results():
    b, d = demo.demo_balance_sheet(), demo.demo_derivatives()
    assert ratios.compute_lcr(b, d, BCBS).ratio > 1.0
    assert ratios.compute_nsfr(b, d, EU).ratio > ratios.compute_nsfr(b, d, BCBS).ratio
    res = {n: stress.run_stress(b, d, s).survival_days for n, s in stress.default_scenarios().items()}
    assert res["Combined"] <= min(res["Idiosyncratic"], res["Market-wide"])


def test_scenario_table_roundtrip():
    scs = stress.default_scenarios()
    back = lio.table_to_scenarios(lio.scenarios_to_table(scs), scs)
    assert back["Combined"].run == scs["Combined"].run
    assert back["Idiosyncratic"].downgrade is True and back["Market-wide"].lag == scs["Market-wide"].lag


def test_validation():
    b = bs([("A_CASH", 100, 0, 0, 0), ("XXX", 1, 0, 0, 0)])
    errs, warns = lio.validate(b)
    assert any("unknown code" in e for e in errs)
    assert warns  # assets and liabilities do not balance


def test_app_runs():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=300).run()
    assert not at.exception and not at.error
    next(r for r in at.radio if r.label == "Regulatory regime").set_value("EU (DR 2015/61 / CRR)").run()
    assert not at.exception
