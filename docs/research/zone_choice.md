# Zone choice reasoning
> Choose **SE3** mainly for consistency and representativeness.

## Why SE3 is a good default

SE3 is the cleanest modelling choice because:

```text
1. It is a major demand zone in Sweden.
2. It is more representative for a generic C&I customer than SE1/SE2.
3. It has enough price variation to make local savings and battery dispatch meaningful.
4. Your Mimer ancillary-market files use SN3/SE3-style area naming, so it keeps FCR/mFRR/spot inputs aligned.
5. Nord Pool and SVK spot data both have SE3, and we already verified they match after timezone alignment.
```

## Why not SE1 or SE2?

SE1 and SE2 are northern Swedish zones. They often behave differently because they are more hydro / generation-heavy and less like a generic urban or industrial C&I demand site.

Using SE1/SE2 may make the case look less representative unless the site is explicitly a northern industrial customer.

## Why not SE4?

SE4 is also defensible, but it is more price-stressed and volatile. It can make the assignment look more like a southern Sweden congestion/price-spread case rather than a neutral representative C&I case.

SE4 is useful as a sensitivity case.

## Final narrative
- SE3 is used as the representative bidding zone because it provides a balanced Swedish C&I case: it is demand-relevant, has meaningful spot-price variation, and is available consistently across the spot, FCR-N, mFRR capacity, and mFRR activation datasets. Other bidding zones are kept out of the main run to avoid mixing market signals across zones.
- SE4 can be used as a sensitivity case to test a higher-price / more constrained southern Sweden scenario.