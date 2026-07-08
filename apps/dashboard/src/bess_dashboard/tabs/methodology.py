from __future__ import annotations

import streamlit as st


def render_methodology_tab() -> None:
    st.markdown('<div class="section-title">Part A model objective</div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            """
            The model treats the battery as a shared behind-the-meter asset.

            **Objective:** maximise total value while protecting local customer savings first.

            ```
            Total value =
                local savings
              + FCR-N capacity revenue
              + mFRR capacity revenue
              + expected mFRR activation value
            ```

            The savings floor is checked at scenario level. Market participation is only considered after
            local site value, SOC limits, peak exposure, and reserve-readiness checks are respected.
            """
        )

    st.markdown('<div class="section-title">Operating priority</div>', unsafe_allow_html=True)

    priority_rows = [
        {
            "Step": "1",
            "Priority": "PV self-consumption",
            "Implementation": "Site PV first serves concurrent factory load before battery or grid decisions.",
        },
        {
            "Step": "2",
            "Priority": "Local battery value",
            "Implementation": "Battery supports peak shaving, high-price discharge, and safe low-price charging.",
        },
        {
            "Step": "3",
            "Priority": "Local reserve protection",
            "Implementation": "Battery preserves near-term reserve headroom for expected peak exposure.",
        },
        {
            "Step": "4",
            "Priority": "FCR-N / mFRR allocation",
            "Implementation": "Remaining feasible capacity is split across FCR-N and mFRR candidates.",
        },
        {
            "Step": "5",
            "Priority": "Uncertainty check",
            "Implementation": "mFRR is evaluated under low, base, and high activation assumptions.",
        },
    ]
    st.dataframe(priority_rows, hide_index=True, width="stretch")

    st.markdown('<div class="section-title">Scenario design</div>', unsafe_allow_html=True)

    scenario_rows = [
        {
            "Scenario": "No battery",
            "Meaning": "PV offsets load directly; remaining demand is imported from grid.",
        },
        {
            "Scenario": "Local-only",
            "Meaning": "Battery is used only for local savings, peak shaving, and safe charging.",
        },
        {
            "Scenario": "FCR-only",
            "Meaning": "Local logic is preserved first, then feasible remaining capacity is committed to FCR-N.",
        },
        {
            "Scenario": "Stacked low activation",
            "Meaning": "Local + FCR-N + mFRR schedule with no expected mFRR activation energy.",
        },
        {
            "Scenario": "Stacked base activation",
            "Meaning": "Uses the processed day’s observed/base mFRR activation probability.",
        },
        {
            "Scenario": "Stacked high activation",
            "Meaning": "Doubles the base mFRR activation probability, capped for stress testing.",
        },
    ]
    st.dataframe(scenario_rows, hide_index=True, width="stretch")

    st.markdown('<div class="section-title">B3 break-even method</div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            """
            B3 asks when stacked FCR-N + mFRR is better than FCR-N-only. This is handled as an
            operational break-even grid, not as a full battery investment model.

            ```
            mFRR is operationally worthwhile when:

            stacked_total_value_eur - fcr_only_total_value_eur > 0
            ```
            """
        )

    break_even_rows = [
        {
            "Input": "mFRR activation probability",
            "Meaning": "Tests activation exposure from 0% to 75%.",
        },
        {
            "Input": "mFRR capacity price multiplier",
            "Meaning": "Tests whether higher or lower mFRR capacity prices compensate for flexibility consumed.",
        },
        {
            "Input": "Battery count",
            "Meaning": "Scales the Part A 1 MW / 2 MWh unit to 1, 2, or 3 identical aggregate batteries.",
        },
        {
            "Input": "FCR-N-only benchmark",
            "Meaning": "Keeps the same site and battery assumptions, with mFRR disabled.",
        },
        {
            "Input": "Daily delta",
            "Meaning": "stacked_total_value_eur minus fcr_only_total_value_eur.",
        },
    ]
    st.dataframe(break_even_rows, hide_index=True, width="stretch")

    st.markdown('<div class="section-title">Commercial payback overlay</div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            """
            Payback is a secondary overlay on top of the operational result. It estimates how long
            incremental mFRR value would take to recover enablement and operating costs.

            ```
            effective_operating_days =
                operating_days * confidence_factor

            annualized_delta_eur =
                daily_delta_vs_fcr_only_eur * effective_operating_days

            annual_net_incremental_value_eur =
                annualized_delta_eur
              - annual_operating_cost_eur
              - risk_buffer_eur

            payback_years =
                upfront_enablement_cost_eur
                /
                annual_net_incremental_value_eur
            ```

            If annual net incremental value is zero or negative, payback is shown as not available.
            """
        )

    payback_rows = [
        {
            "Diagnostic": "Fixed cost burden per day",
            "Formula": "(annual operating cost + risk buffer) / effective operating days",
        },
        {
            "Diagnostic": "Required daily delta for target payback",
            "Formula": (
                "(upfront cost / target payback years + annual operating cost + risk buffer) "
                "/ effective operating days"
            ),
        },
        {
            "Diagnostic": "Gap to target",
            "Formula": "daily delta vs FCR-only - required daily delta for target payback",
        },
    ]
    st.dataframe(payback_rows, hide_index=True, width="stretch")

    st.markdown('<div class="section-title">Constraint logic</div>', unsafe_allow_html=True)

    constraint_rows = [
        {
            "Constraint": "Battery power",
            "Implementation": "Charge or discharge power is capped at 1 MW.",
        },
        {
            "Constraint": "Battery energy",
            "Implementation": "SOC is kept within configured min/max limits.",
        },
        {
            "Constraint": "Shared capacity",
            "Implementation": "Local physical use + local reserve + FCR-N + mFRR cannot exceed 1 MW.",
        },
        {
            "Constraint": "FCR-N headroom",
            "Implementation": "FCR-N commitment requires symmetric SOC buffer.",
        },
        {
            "Constraint": "mFRR readiness",
            "Implementation": "mFRR up commitment requires enough SOC to support possible activation.",
        },
        {
            "Constraint": "Peak protection",
            "Implementation": "Battery reduces peak exposure where feasible; residual exposure is reported.",
        },
        {
            "Constraint": "Savings floor",
            "Implementation": "Scenario-level local savings must clear the configured minimum savings threshold.",
        },
    ]
    st.dataframe(constraint_rows, hide_index=True, width="stretch")

    st.markdown('<div class="section-title">Key assumptions</div>', unsafe_allow_html=True)

    assumption_rows = [
        {"Area": "Battery", "Assumption": "1 MW / 2 MWh lithium-ion BESS."},
        {"Area": "Site", "Assumption": "Representative Swedish C&I light-factory load profile."},
        {"Area": "Zone", "Assumption": "SE3 / SN3 market alignment."},
        {"Area": "Resolution", "Assumption": "Hourly model for Part A; 15-minute data retained as canonical input."},
        {
            "Area": "B3 battery sweep",
            "Assumption": "Battery count scales aggregate MW, MWh, initial SOC, and SOC limits at the same site.",
        },
        {"Area": "PV", "Assumption": "PV is self-consumed by the factory first."},
        {"Area": "FCR-N", "Assumption": "Modelled as capacity revenue requiring SOC headroom."},
        {
            "Area": "mFRR",
            "Assumption": (
                "Modelled as up-capacity plus conservative expected activation value; "
                "base/high activation scenarios also reduce SOC."
            ),
        },
        {
            "Area": "Excluded",
            "Assumption": "FCR-D, aFRR, full battery CAPEX, debt financing, NPV, and IRR are outside scope.",
        },
    ]
    st.dataframe(assumption_rows, hide_index=True, width="stretch")

    st.markdown('<div class="section-title">How to interpret the result</div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            """
            The stacked strategy is not assumed to always beat FCR-only. It performs better when mFRR
            capacity revenue and expected activation value compensate for the battery flexibility consumed
            by activation readiness and expected activation energy.

            In the base and high activation scenarios, expected mFRR activation reduces SOC. This can lower
            later local savings because less energy remains available for peak shaving or high-price discharge.
            The result is the intended Part A trade-off: the battery should not blindly chase ancillary-market
            revenue if doing so weakens the customer-side value case.

            This is a conservative modelling assumption rather than a perfect physical replay of mFRR dispatch.
            """
        )
