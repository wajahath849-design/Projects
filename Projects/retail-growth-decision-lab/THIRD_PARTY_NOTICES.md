# Data and third-party components

## Retail transactions

Chen, D. (2015). *Online Retail*. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33. The source dataset is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

This project removes exact duplicates, classifies merchandise lines, aggregates transactions, derives customer features, and produces model scores. EUR outputs are transformed values, not original source fields.

## Historical exchange rates

European Central Bank, [euro foreign exchange reference rates](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html). The retained CSV is a date-bounded extract of the GBP-per-EUR daily reference series. It is used for analytical reporting translation. Refer to the ECB's [copyright and reuse information](https://www.ecb.europa.eu/services/disclaimer/html/index.en.html) for source terms.

## Dashboard foundation

The dashboard uses the Data app runtime supplied with the OpenAI Data Analytics tooling. The project-specific analytical views live in `dashboard/src/content/`; the runtime provides charts, source inspection, editing, and theme controls. Its assistant and hosted publishing entry points were removed for standalone use. This attribution describes a software dependency and is separate from the project's analytical findings.

React, Recharts, Radix UI, Lexical, Vite, and other npm dependencies retain their respective licenses and notices. Exact installed versions are recorded in `dashboard/package-lock.json`; upstream license files remain in their packages. Python dependency versions are pinned in `requirements.txt`.

This repository does not relicense third-party software or datasets. No project-wide open-source license has been selected for the original project code.
