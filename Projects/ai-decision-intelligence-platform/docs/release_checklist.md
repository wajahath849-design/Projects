# GitHub release checklist

- [ ] Confirm `.env`, `.env.docker`, credentials, raw M5 files, and local artifacts are ignored.
- [ ] Run `scripts/verify_project.py` and retain a passing verification manifest.
- [ ] Confirm unit, integration, end-to-end, lint, type, API, optimization, and Power BI checks.
- [ ] Review README, architecture, model card, data dictionary, API, installation, Power BI,
  interview, and CV documents.
- [ ] Confirm sample data is labeled synthetic and no benchmark claim exceeds measured results.
- [ ] Confirm exactly one production model and zero invalid recommendations.
- [ ] Confirm Docker Compose renders and CI references repository secrets only.
- [ ] Confirm no PBIX or screenshot is claimed unless genuinely generated and opened.
- [ ] Tag a semantic version, write measured release notes, and attach no restricted M5 data.
- [ ] Protect the main branch and require the CI verification job before merge.
