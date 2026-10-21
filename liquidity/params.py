"""
Balance-sheet catalogue with LCR, NSFR and stress treatments.

Sources
-------
* BCBS, Basel III: The Liquidity Coverage Ratio and liquidity risk monitoring
  tools (January 2013), Annexes 1 and 4 - consolidated in Basel Framework LIQ30.
* BCBS, Basel III: The Net Stable Funding Ratio (October 2014), Tables 1-3, and
  the October 2017 statement on derivative liabilities - consolidated in LIQ40.
* EU: Commission Delegated Regulation (EU) 2015/61 (LCR) and CRR Articles 428a
  to 428az (NSFR), as documented in the BCBS RCAP assessments of the EU
  (LCR, July 2017; NSFR, July 2022), and the 2025 decision to keep the reduced
  RSF factors for short-term transactions with financial customers.

Maturity buckets used throughout: d30 (up to 30 days), m6 (31 days to
6 months), m12 (6 to 12 months), y1 (one year or more / no maturity).
"""
from __future__ import annotations

from dataclasses import dataclass

BUCKETS = ["d30", "m6", "m12", "y1"]
BUCKET_LABEL = {"d30": "≤ 30 days", "m6": "31 days – 6 months", "m12": "6 – 12 months",
                "y1": "≥ 1 year / no maturity"}


def F(bcbs, eu=None):
    """A factor that may differ between the BCBS and EU regimes."""
    return {"BCBS": bcbs, "EU": bcbs if eu is None else eu}


# --------------------------------------------------------------------------
# Catalogue
#   lcr: ("hqla", level, haircut) | ("out", rate) | ("in", rate) | None
#        rates / haircuts apply to the d30 bucket (HQLA: total amount)
#   nsfr: factors for (<6m, 6-12m, >=1y)
#   stress: behavioural class used by the survival-horizon engine
# --------------------------------------------------------------------------
CATALOGUE = {
    # ------------------------------------------------------------- assets
    "A_CASH": dict(label="Cash and central bank reserves", side="Asset",
                   lcr=("hqla", "L1", F(0.0)), nsfr=F((0.0, 0.0, 0.0)), stress="cbc_L1"),
    "A_L1_SOV": dict(label="Level 1 securities – sovereigns, central banks, MDBs (unencumbered)", side="Asset",
                     lcr=("hqla", "L1", F(0.0)), nsfr=F((0.05, 0.05, 0.05)), stress="cbc_L1"),
    "A_L1_CB": dict(label="Extremely high-quality covered bonds (EU Level 1; BCBS Level 2A)", side="Asset",
                    lcr=("hqla", F("L2A", "L1CB"), F(0.15, 0.07)), nsfr=F((0.15, 0.15, 0.15), (0.07, 0.07, 0.07)),
                    stress="cbc_L2A"),
    "A_L2A": dict(label="Level 2A securities (20% RW sovereigns, AA- corporates and covered bonds)", side="Asset",
                  lcr=("hqla", "L2A", F(0.15)), nsfr=F((0.15, 0.15, 0.15)), stress="cbc_L2A"),
    "A_L2B_RMBS": dict(label="Level 2B – qualifying RMBS", side="Asset",
                       lcr=("hqla", "L2B", F(0.25)), nsfr=F((0.50, 0.50, 0.50), (0.25, 0.25, 0.25)), stress="cbc_L2B"),
    "A_L2B_CORP": dict(label="Level 2B – corporate bonds A+ to BBB- and equities", side="Asset",
                       lcr=("hqla", "L2B", F(0.50)), nsfr=F((0.50, 0.50, 0.50)), stress="cbc_L2B"),
    "A_L2B_SEC": dict(label="Non-RMBS securitisations (EU Level 2B; not HQLA under BCBS)", side="Asset",
                      lcr=("hqla", F(None, "L2B"), F(1.0, 0.35)), nsfr=F((0.50, 0.50, 0.85), (0.35, 0.35, 0.35)),
                      stress="cbc_nonHQLA"),
    "A_NONHQLA_SEC": dict(label="Non-HQLA securities (marketable)", side="Asset",
                          lcr=None, nsfr=F((0.50, 0.50, 0.85)), stress="cbc_nonHQLA"),
    "A_SEC_ENC_6M": dict(label="Level 1 securities encumbered in repos (< 6 months)", side="Asset",
                         lcr=None, nsfr=F((0.05, 0.05, 0.05)), stress="encumbered"),
    "A_REV_REPO_L1": dict(label="Reverse repos with financials secured by Level 1", side="Asset",
                          lcr=("in", F(0.0)), nsfr=F((0.10, 0.50, 1.00), (0.0, 0.50, 1.00)), stress="in_fin_secured"),
    "A_REV_REPO_OTH": dict(label="Reverse repos with financials secured by non-HQLA", side="Asset",
                           lcr=("in", F(1.0)), nsfr=F((0.15, 0.50, 1.00), (0.05, 0.50, 1.00)), stress="in_fin"),
    "A_FIN_UNSEC": dict(label="Unsecured loans and deposits to financial institutions", side="Asset",
                        lcr=("in", F(1.0)), nsfr=F((0.15, 0.50, 1.00), (0.10, 0.50, 1.00)), stress="in_fin"),
    "A_OPER_DEP": dict(label="Operational deposits held at other banks", side="Asset",
                       lcr=("in", F(0.0, 0.05)), nsfr=F((0.50, 0.50, 0.50)), stress="none"),
    "A_LOAN_NFC": dict(label="Loans to non-financial corporates", side="Asset",
                       lcr=("in", F(0.50)), nsfr=F((0.50, 0.50, 0.85)), stress="in_client"),
    "A_MORTGAGE": dict(label="Residential mortgages (RW ≤ 35%), unencumbered", side="Asset",
                       lcr=("in", F(0.50)), nsfr=F((0.50, 0.50, 0.65)), stress="in_client"),
    "A_MORT_POOL": dict(label="Mortgages encumbered in covered bond cover pool (≥ 1 year)", side="Asset",
                        lcr=None, nsfr=F((1.00, 1.00, 1.00), (0.85, 0.85, 0.85)), stress="encumbered"),
    "A_RETAIL_SME": dict(label="Retail and SME loans (RW > 35%)", side="Asset",
                         lcr=("in", F(0.50)), nsfr=F((0.50, 0.50, 0.85)), stress="in_client"),
    "A_LOAN_SOV": dict(label="Loans to sovereigns and PSEs (RW ≤ 35%)", side="Asset",
                       lcr=("in", F(0.50)), nsfr=F((0.50, 0.50, 0.65)), stress="in_client"),
    "A_IM_POSTED": dict(label="Initial margin posted and CCP default fund", side="Asset",
                        lcr=None, nsfr=F((0.85, 0.85, 0.85)), stress="none"),
    "A_OTHER": dict(label="Fixed assets, non-performing and other assets", side="Asset",
                    lcr=None, nsfr=F((1.00, 1.00, 1.00)), stress="none"),
    # -------------------------------------------------------- liabilities
    "L_CAPITAL": dict(label="Regulatory capital (incl. Tier 2 ≥ 1 year)", side="Liability",
                      lcr=None, asf=F((1.00, 1.00, 1.00)), stress="none"),
    "L_RET_STABLE": dict(label="Retail deposits – stable", side="Liability",
                         lcr=("out", F(0.05)), asf=F((0.95, 0.95, 1.00)), stress="run_retail_stable"),
    "L_RET_LESS": dict(label="Retail deposits – less stable", side="Liability",
                       lcr=("out", F(0.10)), asf=F((0.90, 0.90, 1.00)), stress="run_retail_less"),
    "L_SME": dict(label="Small business deposits", side="Liability",
                  lcr=("out", F(0.10)), asf=F((0.90, 0.90, 1.00)), stress="run_retail_less"),
    "L_OPER": dict(label="Operational deposits (clearing, custody, cash management)", side="Liability",
                   lcr=("out", F(0.25)), asf=F((0.50, 0.50, 1.00)), stress="run_operational"),
    "L_NFC": dict(label="Non-financial corporate deposits (non-operational)", side="Liability",
                  lcr=("out", F(0.40)), asf=F((0.50, 0.50, 1.00)), stress="run_corporate"),
    "L_SOV": dict(label="Sovereign, PSE and MDB deposits", side="Liability",
                  lcr=("out", F(0.40)), asf=F((0.50, 0.50, 1.00)), stress="run_corporate"),
    "L_FIN": dict(label="Deposits from financial institutions", side="Liability",
                  lcr=("out", F(1.00)), asf=F((0.0, 0.50, 1.00)), stress="run_financial"),
    "L_REPO_L1": dict(label="Repos secured by Level 1 assets", side="Liability",
                      lcr=("out", F(0.0)), asf=F((0.0, 0.50, 1.00)), stress="roll_secured_L1"),
    "L_REPO_L2A": dict(label="Repos secured by Level 2A assets", side="Liability",
                       lcr=("out", F(0.15)), asf=F((0.0, 0.50, 1.00)), stress="roll_secured_L2A"),
    "L_REPO_OTH": dict(label="Repos secured by non-HQLA assets", side="Liability",
                       lcr=("out", F(1.00)), asf=F((0.0, 0.50, 1.00)), stress="roll_secured_other"),
    "L_CB_FUND": dict(label="Central bank funding", side="Liability",
                      lcr=("out", F(0.0)), asf=F((0.0, 0.50, 1.00)), stress="roll_secured_L1"),
    "L_BONDS": dict(label="Senior unsecured debt securities issued", side="Liability",
                    lcr=("out", F(1.00)), asf=F((0.0, 0.50, 1.00)), stress="roll_market"),
    "L_COVERED": dict(label="Covered bonds issued", side="Liability",
                      lcr=("out", F(1.00)), asf=F((0.0, 0.50, 1.00)), stress="roll_market"),
    "L_OTHER": dict(label="Other liabilities without stated maturity", side="Liability",
                    lcr=None, asf=F((0.0, 0.0, 0.0)), stress="none"),
    # ------------------------------------------------- off-balance sheet
    "O_CRED_RETAIL": dict(label="Committed credit facilities – retail and SME", side="OBS",
                          lcr=("out", F(0.05)), nsfr=F((0.05, 0.05, 0.05)), stress="draw_retail"),
    "O_CRED_NFC": dict(label="Committed credit facilities – corporates, sovereigns, PSEs", side="OBS",
                       lcr=("out", F(0.10)), nsfr=F((0.05, 0.05, 0.05)), stress="draw_corporate"),
    "O_LIQ_NFC": dict(label="Committed liquidity facilities – corporates, sovereigns, PSEs", side="OBS",
                      lcr=("out", F(0.30)), nsfr=F((0.05, 0.05, 0.05)), stress="draw_corporate"),
    "O_BANKS": dict(label="Committed facilities to banks", side="OBS",
                    lcr=("out", F(0.40)), nsfr=F((0.05, 0.05, 0.05)), stress="draw_financial"),
    "O_LIQ_FIN": dict(label="Committed liquidity facilities to other financials", side="OBS",
                      lcr=("out", F(1.00)), nsfr=F((0.05, 0.05, 0.05)), stress="draw_financial"),
    "O_TRADE": dict(label="Trade finance, guarantees and letters of credit", side="OBS",
                    lcr=("out", F(0.05)), nsfr=F((0.05, 0.05, 0.05)), stress="draw_retail"),
}

LCR_INFLOW_CAP = F(0.75, 0.75)
LCR_INFLOW_CAP_EU_SPECIALISED = 0.90       # DR 2015/61 Art. 33(4), prior approval
LCR_RETAIL_STABLE_3PCT = 0.03              # LIQ30 / DR 2015/61 Art. 24(4), qualifying DGS
NSFR_DERIV_LIAB_RSF = F(0.20, 0.05)        # BCBS 20% (national discretion down to 5%); CRR Art. 428s(2)
EU_L1CB_CAP = 0.70                         # DR 2015/61 Art. 17(2)


@dataclass
class Derivatives:
    """Derivative and collateral inputs (EUR m)."""
    net_outflows_30d: float = 0.0       # net derivative cash outflows (LCR 100%)
    net_inflows_30d: float = 0.0        # net derivative cash inflows (LCR 100%)
    downgrade_collateral: float = 0.0   # 3-notch downgrade collateral calls
    hlba: float = 0.0                   # historical look-back approach (largest 30-day net collateral flow, 24 months)
    nsfr_assets: float = 0.0            # NSFR derivative assets (net of eligible VM)
    nsfr_liabilities: float = 0.0       # NSFR derivative liabilities (net of VM posted)
    gross_liabilities: float = 0.0      # derivative liabilities before VM (basis for the 20% / 5% RSF)


@dataclass
class Regime:
    name: str = "BCBS"
    retail_stable_3pct: bool = False
    eu_specialised_inflow_cap: bool = False

    @property
    def key(self) -> str:
        return "EU" if self.name.startswith("EU") else "BCBS"


def regime(name: str, **kw) -> Regime:
    return Regime(name=name, **kw)
