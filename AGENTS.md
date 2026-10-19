# hermes-triage
Read-only CLI that snapshots the open Hermes Agent issue queue and writes a Markdown queue-health report (response times, age, likely duplicates, suggested labels, repro candidates). Archived 2026-10-19; not deployed.

## Commands
- Check (before every commit and deploy): `./scripts/check.sh`
- Dev: `python3 -m hermes_triage.cli fetch && python3 -m hermes_triage.cli report --out reports/$(date +%F).md`
- Deploy: `./scripts/deploy.sh`

## Non-negotiables
1. Never write to GitHub — no labels, comments or closes. The tool suggests; a person decides. It runs on other people's queue.
2. Only suggest labels that already exist in NousResearch/hermes-agent, and keep every suggestion explainable (a rule match or an issue-form field).
3. Every rule change re-runs the agreement table ("How far to trust the suggestions") on a full snapshot; do not ship a rule that lowers precision.
4. Unaffiliated with Nous Research; README and report say so.
5. Stdlib only: it must run with nothing but Python 3.10+ and a GitHub token.
