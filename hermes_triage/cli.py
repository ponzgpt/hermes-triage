"""hermes-triage: read-only triage of the Hermes Agent issue queue.

    hermes-triage fetch  [--repo OWNER/NAME] [--limit N] [--out data/issues.json]
    hermes-triage report [--in data/issues.json] [--out reports/<date>.md] [--html site/index.html]
"""

import argparse
import json
import sys
from datetime import datetime, timezone

DEFAULT_REPO = "NousResearch/hermes-agent"


def main(argv=None):
    p = argparse.ArgumentParser(prog="hermes-triage", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download open issues to a JSON snapshot")
    f.add_argument("--repo", default=DEFAULT_REPO)
    f.add_argument("--limit", type=int, help="stop after N issues (newest first)")
    f.add_argument("--out", default="data/issues.json")

    r = sub.add_parser("report", help="write a Markdown queue-health report")
    r.add_argument("--in", dest="src", default="data/issues.json")
    r.add_argument("--out", help="default: stdout")
    r.add_argument("--top", type=int, default=15, help="rows per table")
    r.add_argument("--html", help="also write the report as a static HTML page here")

    a = p.parse_args(argv)
    if a.cmd == "fetch":
        from .github import fetch_open_issues
        snap = fetch_open_issues(a.repo, a.limit)
        with open(a.out, "w") as fh:
            json.dump(snap, fh)
        print(f"wrote {len(snap['issues'])} issues to {a.out}", file=sys.stderr)
    else:
        from .report import render
        with open(a.src) as fh:
            snap = json.load(fh)
        md = render(snap, now=datetime.now(timezone.utc), top=a.top)
        if a.out:
            with open(a.out, "w") as fh:
                fh.write(md)
            print(f"wrote {a.out}", file=sys.stderr)
        else:
            sys.stdout.write(md)
        if a.html:
            from .html import to_html
            with open(a.html, "w") as fh:
                fh.write(to_html(md))
            print(f"wrote {a.html}", file=sys.stderr)


if __name__ == "__main__":
    main()
