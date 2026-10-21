"""
Liquidity Dashboard
LCR, NSFR and survival horizon under stress, BCBS (LIQ30/LIQ40) with EU variants.

Author: Laurent Motais de Narbonne
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from liquidity import demo, ratios, stress
from liquidity import io as lio
from liquidity import params as P

st.set_page_config(page_title="Liquidity Dashboard", page_icon="💧", layout="wide")

C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6"
SC_COLOR = {"Idiosyncratic": C1, "Market-wide": C2, "Combined": C3}
GOOD, CRIT = "#0ca30c", "#d03b3b"


def m(x: float) -> str:
    return f"{x:,.0f} m"


def pct(x: float) -> str:
    return "∞" if not np.isfinite(x) else f"{x:.1%}"


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------

st.sidebar.title("💧 Liquidity Dashboard")
st.sidebar.caption("LCR · NSFR · survival horizon under stress")
regime_name = st.sidebar.radio("Regulatory regime", ["BCBS (LIQ30 / LIQ40)", "EU (DR 2015/61 / CRR)"])
is_eu = regime_name.startswith("EU")
with st.sidebar.expander("Discretions"):
    ret3 = st.checkbox("3% outflow for stable retail deposits (qualifying deposit insurance)", False)
    spec = st.checkbox("EU: 90% inflow cap (specialised institutions, prior approval)", False, disabled=not is_eu)
regime = P.regime("EU" if is_eu else "BCBS", retail_stable_3pct=ret3, eu_specialised_inflow_cap=spec and is_eu)
other = P.regime("BCBS" if is_eu else "EU", retail_stable_3pct=ret3)

st.sidebar.subheader("Balance sheet")
src = st.sidebar.radio("Input", ["Demo bank (editable)", "Upload CSV"])
base_bs = demo.demo_balance_sheet()
if src == "Upload CSV":
    up = st.sidebar.file_uploader("Balance sheet (CSV: code, d30, m6, m12, y1)", type=["csv", "txt"])
    if up is not None:
        try:
            base_bs = lio.read_balance_sheet(up)
        except Exception as exc:
            st.sidebar.error(f"Could not read the file: {exc}")
    else:
        st.sidebar.info("Download the template in the **Balance sheet** expander, fill it and upload it.")
st.sidebar.download_button("Download template (demo bank)", demo.demo_balance_sheet().to_csv(index=False).encode(),
                           "liquidity_balance_sheet.csv", "text/csv")

dd = demo.demo_derivatives()
with st.sidebar.expander("Derivatives and collateral (EUR m)"):
    der = P.Derivatives(
        net_outflows_30d=st.number_input("Net derivative outflows (30 days)", 0.0, value=dd.net_outflows_30d),
        net_inflows_30d=st.number_input("Net derivative inflows (30 days)", 0.0, value=dd.net_inflows_30d),
        downgrade_collateral=st.number_input("3-notch downgrade collateral", 0.0, value=dd.downgrade_collateral),
        hlba=st.number_input("Look-back approach (24 months)", 0.0, value=dd.hlba),
        nsfr_assets=st.number_input("NSFR derivative assets", 0.0, value=dd.nsfr_assets),
        nsfr_liabilities=st.number_input("NSFR derivative liabilities", 0.0, value=dd.nsfr_liabilities),
        gross_liabilities=st.number_input("Gross derivative liabilities (before VM)", 0.0, value=dd.gross_liabilities),
    )

# --------------------------------------------------------------------------
# Editors
# --------------------------------------------------------------------------

st.title("Liquidity Dashboard")
st.caption(f"{regime_name} · amounts in EUR million · maturity buckets: ≤30 days, 31 days–6 months, "
           "6–12 months, ≥1 year / no maturity")

with st.expander("Balance sheet by residual maturity (editable)", expanded=False):
    st.caption("Each row is a balance-sheet category with its amounts by residual maturity. Sight deposits go in "
               "the ≤30-day bucket; off-balance-sheet commitments in any bucket (their total is used).")
    bs = st.data_editor(base_bs, num_rows="dynamic", hide_index=True, key=f"bs_{src}", height=420,
                        column_config={
                            "code": st.column_config.SelectboxColumn(options=list(P.CATALOGUE), required=True),
                            "side": st.column_config.TextColumn(disabled=True),
                            "item": st.column_config.TextColumn(disabled=True, width="large"),
                            **{b: st.column_config.NumberColumn(P.BUCKET_LABEL[b], format="%.0f", min_value=0.0)
                               for b in P.BUCKETS}})
    bs = lio.normalise(bs.dropna(subset=["code"]))
    errs, warns = lio.validate(bs)
    for w in warns:
        st.warning(w)
    with st.popover("Category reference (treatments by regime)"):
        st.dataframe(lio.catalogue_table(), hide_index=True)
if errs:
    st.error("Please correct the balance sheet:\n- " + "\n- ".join(errs))
    st.stop()

with st.expander("Stress scenario assumptions (editable)", expanded=False):
    sc_tab = st.data_editor(lio.scenarios_to_table(stress.default_scenarios()), hide_index=True, key="sc",
                            disabled=["parameter"], column_config={
                                "parameter": st.column_config.TextColumn(width="large"),
                                **{k: st.column_config.NumberColumn(format="%.2f") for k in stress.default_scenarios()}})
    scenarios = lio.table_to_scenarios(sc_tab, stress.default_scenarios())

# --------------------------------------------------------------------------
# Calculations
# --------------------------------------------------------------------------

lcr = ratios.compute_lcr(bs, der, regime)
nsfr = ratios.compute_nsfr(bs, der, regime)
lcr_o = ratios.compute_lcr(bs, der, other)
nsfr_o = ratios.compute_nsfr(bs, der, other)
st_res = {n: stress.run_stress(bs, der, s, regime.key) for n, s in scenarios.items()}

tabs = st.tabs(["Overview", "LCR", "NSFR", "Survival horizon", "Methodology"])

# --------------------------------------------------------------------------
# Overview
# --------------------------------------------------------------------------

with tabs[0]:
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("LCR", pct(lcr.ratio), delta=f"{(lcr.ratio - 1):+.1%} vs 100% minimum", delta_color="normal")
    k2.metric("NSFR", pct(nsfr.ratio), delta=f"{(nsfr.ratio - 1):+.1%} vs 100% minimum", delta_color="normal")
    for col, (n, r) in zip([k3, k4, k5], st_res.items()):
        col.metric(f"Survival – {n}", f"{r.survival_days} days" if r.survival_days <= 90 else "> 90 days")

    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        for lbl, val in [("LCR", lcr.ratio), ("NSFR", nsfr.ratio)]:
            fig.add_trace(go.Bar(x=[val], y=[lbl], orientation="h", marker_color=GOOD if val >= 1 else CRIT,
                                 text=[pct(val)], textposition="outside", showlegend=False,
                                 hovertemplate=lbl + ": %{x:.1%}<extra></extra>"))
        fig.add_vline(x=1.0, line=dict(color="#52514e", dash="dash"), annotation_text="100% minimum")
        fig.update_layout(title="Regulatory ratios", margin=dict(l=10, r=10, t=50, b=10), height=260)
        fig.update_xaxes(tickformat=".0%", range=[0, max(lcr.ratio, nsfr.ratio, 1.2) * 1.15])
        st.plotly_chart(fig, width="stretch")
    with c2:
        fig = go.Figure()
        for n, r in st_res.items():
            fig.add_trace(go.Scatter(x=r.daily["day"], y=r.daily["liquidity surplus"], name=n,
                                     line=dict(color=SC_COLOR[n], width=2)))
        fig.add_hline(y=0, line=dict(color=CRIT, width=1))
        fig.update_layout(title="Liquidity surplus under stress (CBC − cumulative net outflows)",
                          hovermode="x unified", margin=dict(l=10, r=10, t=50, b=10), height=260,
                          legend=dict(orientation="h", y=1.18))
        fig.update_xaxes(title="Day")
        fig.update_yaxes(title="EUR m", tickformat=",.0f")
        st.plotly_chart(fig, width="stretch")

    st.subheader("Regime comparison")
    b_l, e_l = (lcr_o, lcr) if is_eu else (lcr, lcr_o)
    b_n, e_n = (nsfr_o, nsfr) if is_eu else (nsfr, nsfr_o)
    comp = pd.DataFrame({
        "BCBS": [b_l.hqla, b_l.net_outflows, b_l.ratio, b_n.total_asf, b_n.total_rsf, b_n.ratio],
        "EU": [e_l.hqla, e_l.net_outflows, e_l.ratio, e_n.total_asf, e_n.total_rsf, e_n.ratio],
    }, index=["HQLA", "Net cash outflows", "LCR", "Available stable funding", "Required stable funding", "NSFR"])

    def fmt_row(v, name):
        return pct(v) if name in ("LCR", "NSFR") else m(v)

    st.dataframe(pd.DataFrame({c: [fmt_row(v, i) for i, v in comp[c].items()] for c in comp}, index=comp.index))
    st.caption("Main EU differences in this book: extremely high-quality covered bonds are Level 1 (7% haircut, "
               "70% cap) and receive a 7% RSF; non-RMBS securitisations are Level 2B; short-term reverse repos and "
               "unsecured loans to financials receive 0% / 5% / 10% RSF instead of 10% / 15% / 15%; cover-pool assets "
               "receive 85% instead of 100%; derivative liabilities attract 5% RSF instead of 20%; operational "
               "deposits held at other banks give a 5% inflow.")

# --------------------------------------------------------------------------
# LCR
# --------------------------------------------------------------------------

with tabs[1]:
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Stock of HQLA", m(lcr.hqla))
    a2.metric("Gross outflows", m(lcr.total_outflows))
    a3.metric("Inflows (after cap)", m(lcr.capped_inflows),
              help=f"Uncapped inflows {lcr.total_inflows:,.0f}; cap = "
                   f"{(P.LCR_INFLOW_CAP_EU_SPECIALISED if regime.eu_specialised_inflow_cap else 0.75):.0%} of outflows")
    a4.metric("LCR", pct(lcr.ratio))
    fig = go.Figure(go.Waterfall(
        x=["Gross outflows", "Inflows (capped)", "Net outflows", "HQLA"],
        measure=["absolute", "relative", "total", "absolute"],
        y=[lcr.total_outflows, -lcr.capped_inflows, 0, lcr.hqla],
        connector=dict(line=dict(color="#c3c2b7")),
        increasing=dict(marker_color=C2), decreasing=dict(marker_color=C3), totals=dict(marker_color=C2)))
    fig.update_layout(title="From outflows to net cash outflows, compared with HQLA", margin=dict(l=10, r=10, t=50, b=10),
                      showlegend=False)
    fig.update_yaxes(title="EUR m", tickformat=",.0f")
    st.plotly_chart(fig, width="stretch")
    st.markdown("**Stock of HQLA**")
    st.dataframe(lcr.hqla_detail.drop(columns="code").style.format(
        {"amount": "{:,.0f}", "haircut": "{:.0%}", "value": "{:,.0f}"}), hide_index=True)
    st.markdown(f"Level 1 {lcr.levels['L1']:,.0f} · Level 1 covered bonds {lcr.levels['L1CB']:,.0f} · Level 2A "
                f"{lcr.levels['L2A']:,.0f} · Level 2B {lcr.levels['L2B']:,.0f} · cap adjustments: 15% "
                f"{lcr.adj15:,.0f}, 40% {lcr.adj40:,.0f}" + (f", 70% {lcr.adj70:,.0f}" if is_eu else ""))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Outflows (30 days)**")
        st.dataframe(lcr.outflows.drop(columns="code").style.format(
            {"amount": "{:,.0f}", "rate": "{:.0%}", "outflow": "{:,.0f}"}), hide_index=True)
    with c2:
        st.markdown("**Inflows (30 days)**")
        st.dataframe(lcr.inflows.drop(columns="code").style.format(
            {"amount": "{:,.0f}", "rate": "{:.0%}", "inflow": "{:,.0f}"}), hide_index=True)

# --------------------------------------------------------------------------
# NSFR
# --------------------------------------------------------------------------

with tabs[2]:
    n1, n2, n3 = st.columns(3)
    n1.metric("Available stable funding", m(nsfr.total_asf))
    n2.metric("Required stable funding", m(nsfr.total_rsf))
    n3.metric("NSFR", pct(nsfr.ratio))
    c1, c2 = st.columns(2)
    for col, df, val, title, color in [(c1, nsfr.asf, "ASF", "Available stable funding by source", C1),
                                       (c2, nsfr.rsf, "RSF", "Required stable funding by use", C2)]:
        d = df.sort_values(val, ascending=True).tail(12)
        fig = go.Figure(go.Bar(x=d[val], y=[s[:45] for s in d["item"]], orientation="h", marker_color=color,
                               hovertemplate="%{y}: %{x:,.0f}<extra></extra>"))
        fig.update_layout(title=title, margin=dict(l=10, r=10, t=50, b=10), height=420)
        fig.update_xaxes(title="EUR m", tickformat=",.0f")
        col.plotly_chart(fig, width="stretch")
    fmt = {"< 6m": "{:,.0f}", "6-12m": "{:,.0f}", "≥ 1y": "{:,.0f}", "ASF": "{:,.0f}", "RSF": "{:,.0f}"}
    show_a = nsfr.asf.assign(factors=nsfr.asf["factors"].map(lambda f: " / ".join(f"{x:.0%}" for x in f)))
    show_r = nsfr.rsf.assign(factors=nsfr.rsf["factors"].map(lambda f: " / ".join(f"{x:.0%}" for x in f)))
    st.markdown("**Available stable funding** (factors for < 6m / 6–12m / ≥ 1y)")
    st.dataframe(show_a.drop(columns="code").style.format(fmt), hide_index=True)
    st.markdown("**Required stable funding**")
    st.dataframe(show_r.drop(columns="code").style.format(fmt), hide_index=True)

# --------------------------------------------------------------------------
# Survival horizon
# --------------------------------------------------------------------------

with tabs[3]:
    sel = st.radio("Scenario", list(st_res), horizontal=True)
    r = st_res[sel]
    s1, s2, s3 = st.columns(3)
    s1.metric("Survival horizon", f"{r.survival_days} days" if r.survival_days <= 90 else "> 90 days")
    s2.metric("Minimum surplus over 90 days", m(r.min_surplus))
    s3.metric("Cumulative net outflows at day 30", m(float(r.daily.loc[29, "cumulative net outflows"])))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=r.daily["day"], y=r.daily["counterbalancing capacity"], name="Counterbalancing capacity",
                             line=dict(color=C1, width=2, shape="hv")))
    fig.add_trace(go.Scatter(x=r.daily["day"], y=r.daily["cumulative net outflows"], name="Cumulative net outflows",
                             line=dict(color=C2, width=2)))
    if r.survival_days <= 90:
        fig.add_vline(x=r.survival_days, line=dict(color=CRIT, dash="dash"),
                      annotation_text=f"survival: {r.survival_days} days")
    fig.update_layout(title=f"{sel} scenario – capacity versus cumulative net outflows", hovermode="x unified",
                      margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="h", y=1.1))
    fig.update_xaxes(title="Day")
    fig.update_yaxes(title="EUR m", tickformat=",.0f")
    st.plotly_chart(fig, width="stretch")

    out_cols = [c for c in r.daily.columns if c.startswith("out: ")]
    comp_fig = go.Figure()
    colors = [C1, C2, C3, C4, "#e87ba4", "#eda100", "#008300"]
    for c, col in zip(out_cols, colors):
        comp_fig.add_trace(go.Scatter(x=r.daily["day"], y=r.daily[c].cumsum(), name=c[5:], stackgroup="out",
                                      line=dict(width=0.5, color=col)))
    comp_fig.update_layout(title="Cumulative gross outflows by source", hovermode="x unified",
                           margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="h", y=1.15))
    comp_fig.update_xaxes(title="Day")
    comp_fig.update_yaxes(title="EUR m", tickformat=",.0f")
    st.plotly_chart(comp_fig, width="stretch")
    c1, c2 = st.columns([2, 3])
    with c1:
        st.markdown("**Counterbalancing capacity**")
        st.dataframe(r.cbc_detail.style.format({"stressed value": "{:,.0f}"}), hide_index=True)
    with c2:
        st.markdown("**Survival horizon by scenario**")
        st.dataframe(pd.DataFrame({
            "Survival (days)": [str(x.survival_days) if x.survival_days <= 90 else "> 90" for x in st_res.values()],
            "Minimum surplus": [x.min_surplus for x in st_res.values()],
        }, index=list(st_res)).style.format({"Minimum surplus": "{:,.0f}"}))
    st.download_button("Download daily ladder (CSV)", r.daily.to_csv(index=False).encode(),
                       f"survival_{sel.lower()}.csv", "text/csv")

# --------------------------------------------------------------------------
# Methodology
# --------------------------------------------------------------------------

with tabs[4]:
    st.markdown(r"""
### LCR (BCBS 2013 / LIQ30; EU Delegated Regulation 2015/61)
$$LCR = \frac{\text{Stock of HQLA}}{\text{Outflows} - \min(\text{Inflows},\ 75\%\times\text{Outflows})} \ge 100\%$$
HQLA = Level 1 + Level 2A + Level 2B − adjustment for the 15% cap − adjustment for the 40% cap, using adjusted
amounts that unwind short-term repos (Annex 1):
* adjustment 15% = max(Adj L2B − 15/85 (Adj L1 + Adj L2A), Adj L2B − 15/60 Adj L1, 0);
* adjustment 40% = max(Adj L2A + Adj L2B − adjustment 15% − 2/3 Adj L1, 0).

Under the EU regime, extremely high-quality covered bonds are Level 1 with a 7% haircut and may not exceed 70% of
the buffer (simplified implementation of DR 2015/61 Article 17(2)).

### NSFR (BCBS 2014 / LIQ40; CRR Articles 428a-428az)
$$NSFR = \frac{\sum_i ASF_i \times \text{liability}_i}{\sum_j RSF_j \times \text{asset}_j + \text{off-balance sheet} + \text{derivatives}} \ge 100\%$$
Derivatives: RSF of 100% on net derivative assets, plus 20% (BCBS; national discretion down to 5%) or 5% (EU) of
gross derivative liabilities.

### EU deviations implemented
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
| Operational deposits held at other banks (LCR inflow) | 0% | 5% (25% if the rate is identified) |
| Inflow cap | 75% | 75% (90% for specialised institutions with approval) |

### Survival horizon
Daily ladder over 90 days:
* **Deposit run-offs**: constant daily hazard calibrated on 30-day rates.
* **Maturing funding**: non-rollover of secured, unsecured and market funding; collateral is released when repos are not rolled over.
* **Facilities**: draw-downs on committed facilities.
* **Inflows**: from maturing loans that are not renewed.
* **Collateral**: a downgrade collateral call.

The counterbalancing capacity combines:
* HQLA after stressed haircuts, available after a monetisation lag;
* non-HQLA securities through repo;
* loans pre-positioned at the central bank.

The survival horizon is the last day on which the capacity exceeds cumulative net outflows.

### Limitations
* Balance sheet by category and maturity bucket, not contract by contract; flows are spread uniformly within buckets.
* Adjusted HQLA amounts only unwind repos secured by Level 2A collateral; collateral received in reverse repos is not
  counted in HQLA.
* Simplified EU 70% cap; other EU specificities (CIUs, cooperative networks, credit unions) are not modelled.
* Stress assumptions are illustrative and should be calibrated in an ILAAP.
""")

st.divider()
st.caption("Built by [Laurent Motais de Narbonne](https://www.linkedin.com/in/laurent-motais-de-narbonne/) · "
           "[Source code](https://github.com/ldenarbonne/liquidity-dashboard) · Based on the BCBS LCR (2013) and NSFR "
           "(2014) standards and the EU LCR Delegated Regulation and CRR. Educational tool, not regulatory advice.")
