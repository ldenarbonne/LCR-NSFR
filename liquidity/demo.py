"""Demonstration balance sheet of a mid-sized universal bank (EUR m, fictitious)."""
from __future__ import annotations

import pandas as pd

from . import params as P

ROWS = [
    # code,               d30,    m6,   m12,     y1
    ("A_CASH",           4000,     0,     0,      0),
    ("A_L1_SOV",          200,   500,   600,   1700),
    ("A_L1_CB",             0,     0,     0,   1500),
    ("A_L2A",               0,     0,   300,   1200),
    ("A_L2B_RMBS",          0,     0,     0,    400),
    ("A_L2B_CORP",          0,     0,     0,    600),
    ("A_L2B_SEC",           0,     0,     0,    300),
    ("A_NONHQLA_SEC",       0,     0,   200,   1000),
    ("A_SEC_ENC_6M",     2000,     0,     0,      0),
    ("A_REV_REPO_L1",    1200,   300,     0,      0),
    ("A_REV_REPO_OTH",    400,   100,     0,      0),
    ("A_FIN_UNSEC",       600,   300,   100,      0),
    ("A_OPER_DEP",        300,     0,     0,      0),
    ("A_LOAN_NFC",        600,  1800,  1400,   5200),
    ("A_MORTGAGE",        120,   600,   700,  10580),
    ("A_MORT_POOL",         0,     0,     0,   4000),
    ("A_RETAIL_SME",      250,   800,   800,   3150),
    ("A_LOAN_SOV",         50,   150,   150,    850),
    ("A_IM_POSTED",         0,     0,     0,    200),
    ("A_OTHER",             0,     0,     0,    800),
    ("L_CAPITAL",           0,     0,     0,   3500),
    ("L_RET_STABLE",    12000,  1200,   500,    300),
    ("L_RET_LESS",       4500,   900,   400,    200),
    ("L_SME",            2600,   300,   100,      0),
    ("L_OPER",           3500,     0,     0,      0),
    ("L_NFC",            3800,   800,   300,    100),
    ("L_SOV",             800,   200,     0,      0),
    ("L_FIN",            1400,   400,   200,      0),
    ("L_REPO_L1",        1500,     0,     0,      0),
    ("L_REPO_L2A",        500,     0,     0,      0),
    ("L_REPO_OTH",        200,     0,     0,      0),
    ("L_CB_FUND",           0,     0,     0,   1000),
    ("L_BONDS",           300,   700,   800,   3200),
    ("L_COVERED",           0,     0,   300,   2700),
    ("L_OTHER",             0,     0,     0,    800),
    ("O_CRED_RETAIL",       0,     0,     0,   2000),
    ("O_CRED_NFC",          0,     0,     0,   6000),
    ("O_LIQ_NFC",           0,     0,     0,   1000),
    ("O_BANKS",             0,     0,     0,    500),
    ("O_LIQ_FIN",           0,     0,     0,    200),
    ("O_TRADE",             0,     0,     0,   1500),
]


def demo_balance_sheet() -> pd.DataFrame:
    df = pd.DataFrame(ROWS, columns=["code"] + P.BUCKETS).astype({b: float for b in P.BUCKETS})
    df.insert(1, "side", [P.CATALOGUE[c]["side"] for c in df["code"]])
    df.insert(2, "item", [P.CATALOGUE[c]["label"] for c in df["code"]])
    return df


def demo_derivatives() -> P.Derivatives:
    return P.Derivatives(net_outflows_30d=150.0, net_inflows_30d=100.0, downgrade_collateral=300.0, hlba=250.0,
                         nsfr_assets=600.0, nsfr_liabilities=500.0, gross_liabilities=1200.0)
