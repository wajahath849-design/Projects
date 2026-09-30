# Campaign experiment proposal

## Decision

Does contacting the proposed audience generate enough incremental contribution to cover contact and offer costs? The historical purchase model cannot answer this question because UCI provides neither randomized campaign assignment nor cost data.

## Design

Freeze the eligible audience, model version, score date, historical value cap, and campaign offer before randomization. Exclude customers who cannot lawfully be contacted using the retailer's actual consent and suppression rules. UCI contains no contact-consent data; the exported list is a historical demonstration, not an actionable mailing list.

Randomize eligible customers 1:1 into campaign and no-contact control within country, recency, and priority-score bands. Assign at customer level, persist the assignment, suppress conflicting campaigns, and analyze everyone in their assigned group (intention to treat). Use one predefined 30-day outcome window and allow a predefined return-processing lag before final contribution reporting.

## Metrics and analysis

Primary: mean realized contribution per randomized customer after returns, actual product costs, contact costs, and offer costs. Estimate treatment minus control with a confidence interval. Secondary: purchase conversion, order count, gross revenue, and return rate. Guardrails: opt-outs, complaints, and contact-frequency limits. Report group balance, assignment integrity, missing costs, and exposure failures before interpreting results.

Choose a minimum economically worthwhile effect before seeing results. For illustration only, detecting a conversion increase from 20% to 23% at two-sided 5% significance and 80% power needs approximately 2,940 customers per arm under a simple normal approximation. This is a planning example, not a power calculation for the contribution metric or the actual selected audience. The historical population has only 3,970 known customers at the decision date, so that example exceeds its capacity. Size the real experiment using prior contribution variance and achievable eligibility; do not claim adequate power from the source alone.

Predefine the analysis date, minimum effect, handling of returns, and decision threshold. Avoid stopping when a favorable result first appears. Segment analyses are exploratory unless powered and prespecified.

## Ranking-policy follow-up

First establish whether the offer works in the eligible audience. Separately compare equal-budget targeting policies (RFM, purchase propensity, and the dashboard's value-times-nonpurchase heuristic) using randomized policy assignment or another valid experimental design. The model's gains curve evaluates natural purchases and does not validate the simulator's priority ordering.

## Launch decision

Roll out only when measured incremental contribution supports the commercial threshold and guardrails pass. If uncertainty includes economically meaningful losses, collect more evidence or revise the offer. Record null or negative findings as outcomes; do not substitute simulated uplift for observed impact.
