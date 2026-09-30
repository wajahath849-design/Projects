# Delivery validation

Original analysis validated on 21 September 2026; EUR conversion and standalone release validated on 28 September 2026 using Windows, Python 3.12.14, pinned analytical dependencies, and headless Microsoft Edge.

On 30 September 2026, the dashboard was rebuilt after applying the Pine & Paper visual theme. The build verified the protected runtime and refreshed both the offline HTML and GitHub Pages demo. The GitHub upload ZIP was regenerated from the staged source and passed its archive integrity check. No browser suite was rerun for this visual-only update.

## Reproducibility and analytical checks

- Ran `python -m pipeline.run` in the project's own `.venv`, starting from the cached official workbook with its verified SHA-256 fingerprint.
- Re-ingested all 541,909 source rows. Removed 5,268 exact duplicate rows; retained 522,504 sales, 8,668 returns, and 5,469 classified exclusions. These mutually exclusive categories reconcile to the original population. Anonymous sales are a subset of retained sales.
- Monthly net revenue and country gross sales reconcile independently to the SQLite ledger.
- No retained sale invoice spans multiple months or multiple identified customers.
- Reproduced selected-model average precision 0.6258428222, top-20% precision 0.6586901763, and RFM average precision 0.5995444889.
- Ten Python tests passed, covering duplicate treatment, anonymous transactions, point-in-time features, exclusive label boundaries, scenario budget/headroom, mature cohort zeros, FX quote direction, weekend handling, and rejection of missing/stale FX rates.
- Four JavaScript tests passed, covering zero-uplift economics, probability headroom, break-even calculation, and CSV assumptions/quoting.

The Windows core-detection utility was unavailable during fitting; joblib used logical cores instead. Training completed successfully and reproduced the earlier metrics.

## Dashboard checks

The protected runtime build verified authored content. Browser checks covered all four tabs at 1440px and 390px widths, with no uncaught page JavaScript errors or page-wide horizontal overflow. Wide tables scroll within their cards. Desktop views and the model/campaign mobile views were visually inspected.

Verified zero-budget behavior, disabled empty export, negative contribution at zero uplift, €0.50 contact-cost formatting, assumption persistence after reload, reset, country filtering, filter persistence, CSV row counts, explicit EUR currency, exported assumptions, and source inspection. Spain filtering produced 25 eligible historical customers and a matching 25-row CSV. All four views were checked for absence of visible ChatGPT and Publish controls. See `browser-checks.json` and the captured preview images in this folder.

The currency step translated 531,172 retained sale/return rows using the frozen ECB extract. Of these, 62,657 used the latest prior published rate; the maximum rate age was two days. EUR monthly net revenue and country gross revenue reconcile to the converted ledger. Model features and predictions remain in their original currency/evaluation configuration. Default scenario contribution is €6,954.99 before display rounding, with the stated hypothetical uplift and margin.

The dashboard builds with standard `npm run build` from source. Packaging verifies the source-snapshot fingerprint and rejects local task metadata in the built HTML. Build dependencies are pinned by the committed npm lockfile. Generated environments, raw data, local databases, caches, and model binaries are excluded from Git.

A clean checkout of the staged Git files independently installed the locked dashboard packages, passed the protected-runtime check, rebuilt and packaged the dashboard, passed all ten Python tests, and verified the 271-row ECB snapshot fingerprint. This is local verification; GitHub-hosted workflows are configured but have not run because the repository has not been uploaded.

The exported single-file HTML was separately opened from disk with network access disabled. Its default 1,000-customer scenario loaded and changing the budget to zero updated the output correctly, with no uncaught page JavaScript errors.

## Scope of these checks

These checks establish reproducibility and basic analytical/UI integrity, not production readiness or causal validity. No campaign has been run. No live data feed, scheduled retraining, public hosting, or monitoring service is configured. Seasonal robustness, external retailer validation, and realized campaign impact remain future work. The experiment proposal defines the next evidence-gathering step.
