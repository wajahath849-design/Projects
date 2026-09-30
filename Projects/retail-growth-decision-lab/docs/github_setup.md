# Upload and publish

The repository is prepared for GitHub but no remote repository or public deployment has been created.

## Upload

Create an empty GitHub repository named `retail-growth-decision-lab`. Upload the contents of the release ZIP, preserving subfolders and dotfiles, or use GitHub Desktop to publish this local folder. Do not upload `.venv`, `node_modules`, raw workbooks, npm caches, or local environment files; they are excluded by `.gitignore` and from the ZIP.

Suggested description: **Retail decision support with SQL, cohort analysis, time-based machine learning, historical EUR conversion, and a campaign simulator.**

Suggested topics: `data-analytics`, `data-science`, `retail`, `sql`, `python`, `machine-learning`, `customer-retention`, `react`.

The demo is already included at `docs/demo/index.html` and opens locally without setup. GitHub's file viewer shows HTML source; use GitHub Pages for a public browser URL.

## Optional GitHub Pages

1. Open repository **Settings → Pages** and choose **GitHub Actions** as the source.
2. Open **Actions → Publish dashboard to GitHub Pages → Run workflow**.
3. When it finishes, use the deployment URL shown by GitHub. Add that URL to the repository About section and your portfolio.

Deployment runs only when manually triggered. The quality-check workflow runs on pushes and pull requests; the Pages workflow rebuilds the dashboard from the committed, reviewed snapshot. Neither workflow downloads the raw retail workbook or retrains the model.

## Before describing the work

Review the methodology and be ready to explain your decisions, the strong RFM baseline, and why simulated contribution is not achieved profit. Keep UCI, ECB, and dependency attribution. Personalize the repository About section with your actual name and links; no identity, employer, or business-impact claims have been invented.

The original project code currently has no selected open-source license. Third-party datasets and dependencies keep their own terms, as described in `THIRD_PARTY_NOTICES.md`.
