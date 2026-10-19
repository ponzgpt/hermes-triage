#!/usr/bin/env sh
# The one check: CI and the release both run this.
set -eu
cd "$(dirname "$0")/.."
python3 -m compileall -q hermes_triage
python3 -m unittest discover -s tests
echo "check passed"
