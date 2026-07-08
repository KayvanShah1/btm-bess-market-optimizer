# Raw data bundle

This bundle uses source-aware filename prefixes.

## Prefix convention

- `esett_` = eSett Open Data profile / imbalance files
- `mimer_` = Svenska Kraftnät Mimer ancillary-market files
- `svk_` = Svenska Kraftnät Open Data files
- `nordpool_` = Nord Pool pasted/exported spot-price reference
- `synthetic_` = generated representative scenario data

## Core recommended model files

- `synthetic_representative_swedish_ci_load_profiles_hourly.csv`
  - Use `light_factory_one_shift_kw` as the primary representative C&I load.
- `esett_production_profile_20260624.csv`
  - Use the solar column as a PV-shape proxy, if using public PV shape.
- `svk_day_ahead_area_prices_20260624.csv` or `nordpool_day_ahead_prices_pasted_20260624.csv`
  - Use one consistently as `spot_price_eur_mwh`.
- `mimer_fcr_capacity_market_20260624.csv`
  - Use FCR-N price for the FCR-only baseline.
- `mimer_mfrr_capacity_market_d1_20260624.csv`
  - Use mFRR up capacity price for mFRR capacity revenue.
- `mimer_mfrr_energy_activation_market_20260624.csv`
  - Use mFRR activation energy price and activation flags/volumes.

## Files intentionally excluded

- Earlier FCR file from another date
- C&I profile summary CSV
- C&I profile PNG plot

See `raw_data_manifest.csv` for the exact mapping from previous filenames to source-prefixed filenames.
