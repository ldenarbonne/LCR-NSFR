"""
Survival horizon under stress: daily cash-flow ladder over 90 days with a
counterbalancing capacity (CBC).

Behaviour is driven by scenario parameters (30-day run-off / draw-down rates,
rollover rates, stressed haircuts and monetisation lags). Contractual
maturities are spread uniformly within their bucket (d30 over days 1-30,
m6 over days 31-180). Deposit run-offs follow a constant daily hazard
calibrated on the 30-day rate. This is an internal stress-testing tool in the
spirit of the ILAAP, not a regulatory metric.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import params as P

H = 90


@dataclass
class Scenario:
    name: str
    run: dict                     # 30-day run-off rates by stress class
    roll: dict                    # rollover rates of maturing funding
    lending_rollover: float       # share of maturing client loans renewed
    draw: dict                    # 30-day draw-down rates of committed facilities
    downgrade: bool               # collateral calls on day 1
    extra_haircut: dict           # additional haircuts on CBC by class
    lag: dict                     # first day each CBC class can be monetised
    nonhqla_repo_haircut: float
    cb_access: bool = True
    cb_pledgeable_share: float = 0.25   # share of unencumbered client loans pre-positioned at the central bank
    cb_haircut: float = 0.40
    cb_lag: int = 5


def default_scenarios() -> dict[str, Scenario]:
    idio = Scenario(
        "Idiosyncratic",
        run=dict(run_retail_stable=0.07, run_retail_less=0.15, run_operational=0.20, run_corporate=0.40,
                 run_financial=1.00),
        roll=dict(roll_secured_L1=1.00, roll_secured_L2A=0.75, roll_secured_other=0.25, roll_market=0.0),
        lending_rollover=0.75,
        draw=dict(draw_retail=0.05, draw_corporate=0.20, draw_financial=0.50),
        downgrade=True,
        extra_haircut=dict(cbc_L1=0.0, cbc_L2A=0.0, cbc_L2B=0.05, cbc_nonHQLA=0.0),
        lag=dict(cbc_L1=1, cbc_L2A=2, cbc_L2B=3, cbc_nonHQLA=5),
        nonhqla_repo_haircut=0.25,
    )
    market = Scenario(
        "Market-wide",
        run=dict(run_retail_stable=0.04, run_retail_less=0.08, run_operational=0.15, run_corporate=0.25,
                 run_financial=0.50),
        roll=dict(roll_secured_L1=1.00, roll_secured_L2A=0.50, roll_secured_other=0.0, roll_market=0.25),
        lending_rollover=0.90,
        draw=dict(draw_retail=0.05, draw_corporate=0.25, draw_financial=0.40),
        downgrade=False,
        extra_haircut=dict(cbc_L1=0.0, cbc_L2A=0.10, cbc_L2B=0.20, cbc_nonHQLA=0.0),
        lag=dict(cbc_L1=1, cbc_L2A=3, cbc_L2B=5, cbc_nonHQLA=10),
        nonhqla_repo_haircut=0.50,
    )
    comb = Scenario(
        "Combined",
        run={k: max(idio.run[k], market.run[k]) for k in idio.run},
        roll={k: min(idio.roll[k], market.roll[k]) for k in idio.roll},
        lending_rollover=max(idio.lending_rollover, market.lending_rollover),
        draw={k: max(idio.draw[k], market.draw[k]) for k in idio.draw},
        downgrade=True,
        extra_haircut={k: max(idio.extra_haircut[k], market.extra_haircut[k]) for k in idio.extra_haircut},
        lag={k: max(idio.lag[k], market.lag[k]) for k in idio.lag},
        nonhqla_repo_haircut=max(idio.nonhqla_repo_haircut, market.nonhqla_repo_haircut),
    )
    return {s.name: s for s in (idio, market, comb)}


# --------------------------------------------------------------------------


def _uniform(amount: float, start: int, end: int) -> np.ndarray:
    """Spread an amount uniformly over days start..end (1-based, inclusive), truncated at H."""
    x = np.zeros(H + 1)
    n = end - start + 1
    lo, hi = start, min(end, H)
    if hi >= lo:
        x[lo:hi + 1] = amount / n
    return x


def _hazard(balance: float, r30: float) -> np.ndarray:
    """Daily outflows from a balance running off at a constant daily hazard."""
    x = np.zeros(H + 1)
    if balance <= 0 or r30 <= 0:
        return x
    lam = 1 - (1 - min(r30, 0.999999)) ** (1 / 30)
    days = np.arange(1, H + 1)
    remaining = balance * (1 - lam) ** (days - 1)
    x[1:] = remaining * lam
    if r30 >= 1:
        x[1:] = 0.0
        x[1:31] = balance / 30
    return x


@dataclass
class StressResult:
    scenario: str
    daily: pd.DataFrame
    survival_days: int
    min_surplus: float
    cbc_detail: pd.DataFrame


def run_stress(bs: pd.DataFrame, der: P.Derivatives, sc: Scenario, regime_key: str = "BCBS") -> StressResult:
    out = {g: np.zeros(H + 1) for g in ["Retail & SME deposits", "Corporate & public deposits",
                                         "Financial deposits", "Secured funding", "Market funding",
                                         "Facility draw-downs", "Derivatives & collateral"]}
    inflow = np.zeros(H + 1)
    cbc_add = {k: np.zeros(H + 1) for k in ["cbc_L1", "cbc_L2A", "cbc_L2B", "cbc_nonHQLA"]}
    stocks = {k: 0.0 for k in cbc_add}
    cb_pool = 0.0

    for _, r in bs.iterrows():
        cat = P.CATALOGUE.get(r["code"])
        if cat is None:
            continue
        cls = cat["stress"]
        d30, m6 = float(r["d30"]), float(r["m6"])
        total = float(r[P.BUCKETS].sum())
        if cls.startswith("cbc_"):
            lcr = cat["lcr"]
            if lcr and lcr[0] == "hqla":
                hc = lcr[2][regime_key]
                level = lcr[1][regime_key] if isinstance(lcr[1], dict) else lcr[1]
                if level is None:          # non-HQLA under this regime: repo market only
                    stocks["cbc_nonHQLA"] += total * (1 - sc.nonhqla_repo_haircut)
                    continue
                key = cls if level != "L1CB" else "cbc_L1"
                stocks[key] += total * max(1 - hc - sc.extra_haircut.get(key, 0.0), 0.0)
            else:
                stocks["cbc_nonHQLA"] += total * (1 - sc.nonhqla_repo_haircut)
        elif cls.startswith("run_"):
            rate = sc.run[cls]
            group = ("Retail & SME deposits" if "retail" in cls else
                     "Financial deposits" if "financial" in cls else "Corporate & public deposits")
            out[group] += _hazard(d30, rate) + _uniform(m6 * rate, 31, 180)
        elif cls.startswith("roll_secured"):
            roll = sc.roll[cls]
            mat = _uniform(d30, 1, 30) + _uniform(m6, 31, 180)
            out["Secured funding"] += mat * (1 - roll)
            # collateral released by funding that is not rolled over
            back = {"roll_secured_L1": "cbc_L1", "roll_secured_L2A": "cbc_L2A",
                    "roll_secured_other": "cbc_nonHQLA"}[cls]
            factor = 1.0 if back == "cbc_L1" else (1 - sc.extra_haircut.get(back, 0.0)) if back == "cbc_L2A" \
                else (1 - sc.nonhqla_repo_haircut)
            cbc_add[back] += mat * (1 - roll) * factor
        elif cls == "roll_market":
            mat = _uniform(d30, 1, 30) + _uniform(m6, 31, 180)
            out["Market funding"] += mat * (1 - sc.roll["roll_market"])
        elif cls.startswith("draw_"):
            out["Facility draw-downs"] += _hazard(total, sc.draw[cls])
        elif cls == "in_client":
            inflow += (_uniform(d30, 1, 30) + _uniform(m6, 31, 180)) * (1 - sc.lending_rollover)
            cb_pool += float(r["y1"]) * sc.cb_pledgeable_share
        elif cls in ("in_fin", "in_fin_secured"):
            inflow += _uniform(d30, 1, 30) + _uniform(m6, 31, 180)
    # derivatives
    out["Derivatives & collateral"] += _uniform(der.net_outflows_30d, 1, 30)
    inflow += _uniform(der.net_inflows_30d, 1, 30)
    if sc.downgrade:
        out["Derivatives & collateral"][1] += der.downgrade_collateral

    # counterbalancing capacity available by day t
    days = np.arange(H + 1)
    cbc = np.zeros(H + 1)
    det = []
    for k, v in stocks.items():
        lag = sc.lag[k]
        avail = np.where(days >= lag, v, 0.0)
        cbc += avail
        det.append({"source": k.replace("cbc_", ""), "stressed value": v, "available from day": lag})
    if sc.cb_access and cb_pool > 0:
        cbv = cb_pool * (1 - sc.cb_haircut)
        cbc += np.where(days >= sc.cb_lag, cbv, 0.0)
        det.append({"source": "Central bank (pre-positioned loans)", "stressed value": cbv,
                    "available from day": sc.cb_lag})
    released = sum(np.cumsum(v) for v in cbc_add.values())
    cbc = cbc + released

    total_out = sum(out.values())
    cum_out = np.cumsum(total_out)
    cum_in = np.cumsum(inflow)
    surplus = cbc - cum_out + cum_in
    surplus[0] = cbc[0]
    neg = np.where(surplus[1:] < 0)[0]
    survival = int(neg[0]) if len(neg) else H + 1      # last day with a positive surplus
    daily = pd.DataFrame({"day": days, **{f"out: {g}": v for g, v in out.items()},
                          "outflows": total_out, "inflows": inflow, "cumulative net outflows": cum_out - cum_in,
                          "counterbalancing capacity": cbc, "liquidity surplus": surplus})
    return StressResult(sc.name, daily.iloc[1:].reset_index(drop=True), survival,
                        float(surplus[1:].min()), pd.DataFrame(det))
