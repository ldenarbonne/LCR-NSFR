"""Balance-sheet and scenario tables: import, validation, conversion."""
from __future__ import annotations

import io

import numpy as np
import pandas as pd

from . import params as P
from .stress import Scenario

SCENARIO_ROWS = [
    ("run", "run_retail_stable", "30-day run-off – retail stable"),
    ("run", "run_retail_less", "30-day run-off – retail less stable and SME"),
    ("run", "run_operational", "30-day run-off – operational deposits"),
    ("run", "run_corporate", "30-day run-off – corporate and public deposits"),
    ("run", "run_financial", "30-day run-off – financial deposits"),
    ("roll", "roll_secured_L1", "Rollover – repos on Level 1 and central bank"),
    ("roll", "roll_secured_L2A", "Rollover – repos on Level 2A"),
    ("roll", "roll_secured_other", "Rollover – repos on other collateral"),
    ("roll", "roll_market", "Rollover – debt securities and covered bonds"),
    ("x", "lending_rollover", "Share of maturing client loans renewed"),
    ("draw", "draw_retail", "30-day draw-down – retail facilities and trade finance"),
    ("draw", "draw_corporate", "30-day draw-down – corporate facilities"),
    ("draw", "draw_financial", "30-day draw-down – financial facilities"),
    ("x", "downgrade", "Downgrade collateral call on day 1 (1 = yes)"),
    ("extra_haircut", "cbc_L2A", "Additional haircut – Level 2A"),
    ("extra_haircut", "cbc_L2B", "Additional haircut – Level 2B"),
    ("x", "nonhqla_repo_haircut", "Repo haircut – non-HQLA securities"),
    ("lag", "cbc_L2A", "Monetisation lag (days) – Level 2A"),
    ("lag", "cbc_L2B", "Monetisation lag (days) – Level 2B"),
    ("lag", "cbc_nonHQLA", "Monetisation lag (days) – non-HQLA"),
    ("x", "cb_access", "Central bank access (1 = yes)"),
    ("x", "cb_pledgeable_share", "Share of long-term loans pre-positioned at the central bank"),
    ("x", "cb_haircut", "Central bank haircut on pre-positioned loans"),
    ("x", "cb_lag", "Central bank lag (days)"),
]


def scenarios_to_table(scs: dict[str, Scenario]) -> pd.DataFrame:
    rows = []
    for grp, key, label in SCENARIO_ROWS:
        row = {"parameter": label}
        for name, s in scs.items():
            v = getattr(s, grp)[key] if grp != "x" else getattr(s, key)
            row[name] = float(v)
        rows.append(row)
    return pd.DataFrame(rows)


def table_to_scenarios(df: pd.DataFrame, template: dict[str, Scenario]) -> dict[str, Scenario]:
    import copy
    out = {}
    for name, base in template.items():
        s = copy.deepcopy(base)
        for (grp, key, _), (_, row) in zip(SCENARIO_ROWS, df.iterrows()):
            v = float(row[name])
            if grp == "x":
                cur = getattr(s, key)
                setattr(s, key, bool(round(v)) if isinstance(cur, bool) else (int(round(v)) if isinstance(cur, int) else v))
            elif grp == "lag":
                getattr(s, grp)[key] = int(round(v))
            else:
                getattr(s, grp)[key] = v
        out[name] = s
    return out


def read_balance_sheet(file) -> pd.DataFrame:
    content = file.read() if hasattr(file, "read") else open(file, "rb").read()
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")
    df = pd.read_csv(io.StringIO(content), sep=None, engine="python")
    df.columns = [c.strip().lower() for c in df.columns]
    return normalise(df)


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for b in P.BUCKETS:
        if b not in d:
            d[b] = 0.0
        d[b] = pd.to_numeric(d[b], errors="coerce").fillna(0.0)
    d["code"] = d["code"].astype(str).str.strip().str.upper()
    d["side"] = [P.CATALOGUE[c]["side"] if c in P.CATALOGUE else "?" for c in d["code"]]
    d["item"] = [P.CATALOGUE[c]["label"] if c in P.CATALOGUE else "Unknown code" for c in d["code"]]
    return d[["code", "side", "item"] + P.BUCKETS]


def validate(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    for i, r in df.iterrows():
        if r["code"] not in P.CATALOGUE:
            errors.append(f"Row {i + 2}: unknown code '{r['code']}'")
        if (r[P.BUCKETS] < 0).any():
            errors.append(f"Row {i + 2}: negative amounts are not allowed")
    a = df.loc[df["side"] == "Asset", P.BUCKETS].to_numpy().sum()
    l = df.loc[df["side"] == "Liability", P.BUCKETS].to_numpy().sum()
    if a > 0 and abs(a - l) / a > 0.005:
        warnings.append(f"Total assets ({a:,.0f}) and liabilities ({l:,.0f}) differ by {a - l:,.0f}.")
    return errors, warnings


def catalogue_table() -> pd.DataFrame:
    rows = []
    for code, c in P.CATALOGUE.items():
        lcr = c["lcr"]
        if lcr is None:
            l_b = l_e = "–"
        elif lcr[0] == "hqla":
            def fmt(k):
                lvl = lcr[1][k] if isinstance(lcr[1], dict) else lcr[1]
                return "not HQLA" if lvl is None else f"{lvl}, haircut {lcr[2][k]:.0%}"
            l_b, l_e = fmt("BCBS"), fmt("EU")
        else:
            word = "outflow" if lcr[0] == "out" else "inflow"
            l_b, l_e = f"{word} {lcr[1]['BCBS']:.0%}", f"{word} {lcr[1]['EU']:.0%}"
        f = c.get("asf") or c.get("nsfr")
        nb = " / ".join(f"{x:.0%}" for x in f["BCBS"])
        ne = " / ".join(f"{x:.0%}" for x in f["EU"])
        rows.append({"code": code, "side": c["side"], "item": c["label"], "LCR – BCBS": l_b, "LCR – EU": l_e,
                     "NSFR (<6m / 6-12m / ≥1y) – BCBS": nb, "NSFR – EU": ne,
                     "stress class": c["stress"]})
    return pd.DataFrame(rows)
