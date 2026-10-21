"""LCR (LIQ30 / DR 2015/61) and NSFR (LIQ40 / CRR Part Six Title IV)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import params as P

# ==========================================================================
# LCR
# ==========================================================================


def _val(x, key):
    return x[key] if isinstance(x, dict) else x


@dataclass
class LCRResult:
    hqla_detail: pd.DataFrame
    outflows: pd.DataFrame
    inflows: pd.DataFrame
    hqla: float
    adj15: float
    adj40: float
    adj70: float
    total_outflows: float
    total_inflows: float
    capped_inflows: float
    net_outflows: float
    ratio: float
    levels: dict


def hqla_stock(L1: float, L1CB: float, L2A: float, L2B: float, adj: dict, regime: P.Regime):
    """Stock of HQLA after the 15% / 40% caps (LCR Annex 1) and, under the EU
    regime, the 70% cap on Level 1 covered bonds (DR 2015/61 Art. 17(2)).

    ``adj`` holds the adjusted amounts (after unwinding short-term secured
    funding transactions); ``L1CB`` is zero under the BCBS regime.
    """
    a1 = adj["L1"] + adj["L1CB"]
    a2a, a2b = adj["L2A"], adj["L2B"]
    adj15 = max(a2b - 15 / 85 * (a1 + a2a), a2b - 15 / 60 * a1, 0.0)
    adj40 = max(a2a + a2b - adj15 - 2 / 3 * a1, 0.0)
    level2 = L2A + L2B - adj15 - adj40
    adj70 = 0.0
    if regime.key == "EU" and L1CB > 0:
        # simplified: Level 1 covered bonds may not exceed 70% of the buffer,
        # ie L1CB <= 7/3 x (other Level 1 + eligible Level 2)
        adj70 = max(L1CB - 7 / 3 * (L1 + level2), 0.0)
    stock = L1 + L1CB + L2A + L2B - adj15 - adj40 - adj70
    return stock, adj15, adj40, adj70


def compute_lcr(bs: pd.DataFrame, der: P.Derivatives, regime: P.Regime) -> LCRResult:
    k = regime.key
    rows_h, rows_o, rows_i = [], [], []
    lv = {"L1": 0.0, "L1CB": 0.0, "L2A": 0.0, "L2B": 0.0}
    for _, r in bs.iterrows():
        cat = P.CATALOGUE.get(r["code"])
        if cat is None or cat["lcr"] is None:
            continue
        kind = cat["lcr"][0]
        total = float(r[P.BUCKETS].sum())
        d30 = float(r["d30"])
        if kind == "hqla":
            level = _val(cat["lcr"][1], k)
            hc = _val(cat["lcr"][2], k)
            if level is None:
                continue
            value = total * (1 - hc)
            lv[level] += value
            rows_h.append({"code": r["code"], "item": cat["label"], "level": level, "amount": total,
                           "haircut": hc, "value": value})
        elif kind == "out":
            rate = _val(cat["lcr"][1], k)
            if r["code"] == "L_RET_STABLE" and regime.retail_stable_3pct:
                rate = P.LCR_RETAIL_STABLE_3PCT
            base = total if cat["side"] == "OBS" else d30
            rows_o.append({"code": r["code"], "item": cat["label"], "amount": base, "rate": rate,
                           "outflow": base * rate})
        elif kind == "in":
            rate = _val(cat["lcr"][1], k)
            rows_i.append({"code": r["code"], "item": cat["label"], "amount": d30, "rate": rate,
                           "inflow": d30 * rate})
    # derivatives and collateral (LCR Annex 4, section D)
    for code, label, amt in [("D_NET_OUT", "Net derivative cash outflows", der.net_outflows_30d),
                             ("D_DOWNGRADE", "Collateral calls – 3-notch downgrade", der.downgrade_collateral),
                             ("D_HLBA", "Market valuation changes (look-back approach)", der.hlba)]:
        if amt:
            rows_o.append({"code": code, "item": label, "amount": amt, "rate": 1.0, "outflow": amt})
    if der.net_inflows_30d:
        rows_i.append({"code": "D_NET_IN", "item": "Net derivative cash inflows", "amount": der.net_inflows_30d,
                       "rate": 1.0, "inflow": der.net_inflows_30d})

    # adjusted amounts: unwind repos <= 30 days secured by Level 2A / non-Level-1 collateral
    rep = bs.set_index("code")["d30"] if len(bs) else pd.Series(dtype=float)
    repo_l2a = float(rep.get("L_REPO_L2A", 0.0))
    adj = {"L1": lv["L1"] - repo_l2a, "L1CB": lv["L1CB"], "L2A": lv["L2A"] + repo_l2a, "L2B": lv["L2B"]}
    stock, adj15, adj40, adj70 = hqla_stock(lv["L1"], lv["L1CB"], lv["L2A"], lv["L2B"], adj, regime)

    out = pd.DataFrame(rows_o, columns=["code", "item", "amount", "rate", "outflow"])
    inn = pd.DataFrame(rows_i, columns=["code", "item", "amount", "rate", "inflow"])
    tot_out = float(out["outflow"].sum())
    tot_in = float(inn["inflow"].sum())
    cap = P.LCR_INFLOW_CAP_EU_SPECIALISED if (k == "EU" and regime.eu_specialised_inflow_cap) else _val(P.LCR_INFLOW_CAP, k)
    capped = min(tot_in, cap * tot_out)
    net = tot_out - capped
    ratio = stock / net if net > 0 else np.inf
    return LCRResult(pd.DataFrame(rows_h), out, inn, stock, adj15, adj40, adj70, tot_out, tot_in, capped, net,
                     ratio, lv)


# ==========================================================================
# NSFR
# ==========================================================================


@dataclass
class NSFRResult:
    asf: pd.DataFrame
    rsf: pd.DataFrame
    total_asf: float
    total_rsf: float
    ratio: float


def compute_nsfr(bs: pd.DataFrame, der: P.Derivatives, regime: P.Regime) -> NSFRResult:
    k = regime.key
    rows_a, rows_r = [], []
    for _, r in bs.iterrows():
        cat = P.CATALOGUE.get(r["code"])
        if cat is None:
            continue
        lt6, m12, y1 = float(r["d30"] + r["m6"]), float(r["m12"]), float(r["y1"])
        if cat["side"] == "Liability":
            f = _val(cat["asf"], k)
            w = lt6 * f[0] + m12 * f[1] + y1 * f[2]
            rows_a.append({"code": r["code"], "item": cat["label"], "< 6m": lt6, "6-12m": m12, "≥ 1y": y1,
                           "factors": f, "ASF": w})
        else:
            f = _val(cat["nsfr"], k)
            w = lt6 * f[0] + m12 * f[1] + y1 * f[2]
            rows_r.append({"code": r["code"], "item": cat["label"], "< 6m": lt6, "6-12m": m12, "≥ 1y": y1,
                           "factors": f, "RSF": w})
    # derivatives (NSFR paragraphs 19-21, 43; CRR Art. 428s(2))
    net = der.nsfr_assets - der.nsfr_liabilities
    if net > 0:
        rows_r.append({"code": "D_NET_ASSET", "item": "NSFR derivative assets net of liabilities", "< 6m": 0,
                       "6-12m": 0, "≥ 1y": net, "factors": (1.0, 1.0, 1.0), "RSF": net})
    rf = _val(P.NSFR_DERIV_LIAB_RSF, k)
    if der.gross_liabilities:
        rows_r.append({"code": "D_LIAB_ADDON", "item": f"{rf:.0%} of gross derivative liabilities", "< 6m": 0,
                       "6-12m": 0, "≥ 1y": der.gross_liabilities, "factors": (rf, rf, rf),
                       "RSF": rf * der.gross_liabilities})
    asf = pd.DataFrame(rows_a)
    rsf = pd.DataFrame(rows_r)
    ta, tr = float(asf["ASF"].sum()), float(rsf["RSF"].sum())
    return NSFRResult(asf, rsf, ta, tr, ta / tr if tr > 0 else np.inf)
