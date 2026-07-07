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
        {"Area": "PV", "Assumption": "PV is self-consumed by the factory first."},
        {"Area": "FCR-N", "Assumption": "Modelled as capacity revenue requiring SOC headroom."},
        {"Area": "mFRR", "Assumption": "Modelled as up-capacity plus expected activation value."},
        {
            "Area": "Excluded",
            "Assumption": "FCR-D, aFRR, PV export revenue, and machine scheduling are outside core Part A.",
        },
    ]
    st.dataframe(assumption_rows, hide_index=True, width="stretch")

    st.markdown('<div class="section-title">How to interpret the result</div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            """
            The stacked strategy is not assumed to always beat FCR-only. It performs better when mFRR
            capacity revenue is attractive and activation exposure is low. Under base or high activation
            assumptions, mFRR can reduce total value because expected activation uses battery energy and
            leaves less flexibility for local site savings.

            This is the intended Part A trade-off: the battery should not blindly chase ancillary-market
            revenue if doing so weakens the customer-side value case.
            """
        )
