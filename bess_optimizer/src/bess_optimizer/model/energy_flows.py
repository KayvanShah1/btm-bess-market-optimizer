from __future__ import annotations


def split_pv_and_load(site_load_kw: float, site_pv_kw: float) -> dict[str, float]:
    pv_to_load_kw = min(site_load_kw, site_pv_kw)
    remaining_load_kw = max(site_load_kw - site_pv_kw, 0.0)
    pv_surplus_kw = max(site_pv_kw - site_load_kw, 0.0)

    return {
        "pv_to_load_kw": pv_to_load_kw,
        "remaining_load_kw": remaining_load_kw,
        "pv_surplus_kw": pv_surplus_kw,
    }

