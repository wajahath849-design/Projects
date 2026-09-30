# Interview guide

## 60-second introduction

“Retail Growth Decision Lab asks how a retailer can use customer history to plan outreach under a limited budget. I used 541,909 real UCI transaction rows, built an audited SQL ledger, measured revenue and cohort retention, and trained a 30-day repeat-purchase model with time-based validation. On the November holdout, the selected model reached 65.9% precision in the top 20% versus 63.2% for a strong RFM baseline. The dashboard also explores campaign economics using a separate, transparent priority heuristic. I distinguish natural purchase prediction from causal uplift and propose a randomized experiment to measure actual impact.”

## Design decisions to explain

**Why not a random train/test split?** Customer behavior and seasonality change over time. A random split lets later patterns influence an unrealistically earlier decision. Monthly cutoffs recreate how the model would have been used.

**Why average precision?** The positive class is not rare enough to make accuracy meaningless, but the business acts on a ranked subset. Average precision and top-capacity metrics measure that job directly.

**Why compare with recency?** A simple operational rule can be cheap and strong. Machine learning is useful only if it beats a credible decision baseline.

**Why add RFM?** Recency alone understates what a simple customer model can do. A logistic baseline using recency, frequency, and monetary value captures much of the signal. The selected model improves average precision by about 0.026 over RFM, so deployment complexity needs to be justified against that modest benefit.

**Why calibrate probabilities?** Ranking metrics do not ensure that a 40% score means roughly 40% observed incidence. Scenario calculations require probabilities with interpretable scale.

**Why is the campaign simulator not an ROI calculator?** The dataset has no treatment assignment, margin, or campaign cost. The simulator exposes assumptions and recommends a randomized experiment instead of presenting scenario output as achieved value.

**What would you build next?** Run a stratified randomized campaign, log eligibility and assignment, measure incremental contribution, inspect heterogeneous treatment effects, and replace the heuristic only after out-of-sample uplift validation.

## Likely critique

The November period may be seasonally unusual, customers repeat across training snapshots, the data is from one historical retailer, exact duplicates are not provably errors, and the model lacks product-level or marketing context. These are disclosed limitations. The project demonstrates decision discipline rather than claiming universal model performance.
