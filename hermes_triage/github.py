"""Fetch open issues (not pull requests) from GitHub's GraphQL API.

Read-only: this module never writes to GitHub. The token comes from
GITHUB_TOKEN, or from `gh auth token` when the GitHub CLI is logged in.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request

API = "https://api.github.com/graphql"

QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(states: OPEN, first: 100, after: $cursor,
           orderBy: {field: CREATED_AT, direction: DESC}) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        number title body url createdAt updatedAt
        authorAssociation
        author { __typename login }
        labels(first: 30) { nodes { name } }
        comments(first: 10) {
          totalCount
          nodes { createdAt authorAssociation author { __typename login } }
        }
      }
    }
  }
}
"""

# Bodies are only read for classification and duplicate detection; the first
# few kilobytes carry the template fields and the error message.
BODY_LIMIT = 4000


def token():
    t = os.environ.get("GITHUB_TOKEN")
    if t:
        return t
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        sys.exit("hermes-triage: set GITHUB_TOKEN or log in with `gh auth login`")


def _post(payload, tok, retries=4):
    req = urllib.request.Request(
        API, data=json.dumps(payload).encode(),
        headers={"Authorization": f"bearer {tok}", "User-Agent": "hermes-triage"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
            if "errors" in data:
                raise RuntimeError(data["errors"])
            return data["data"]
        except Exception as e:  # network blips and GitHub 502s on big pages
            if attempt == retries - 1:
                raise
            print(f"  retrying after {e!r}", file=sys.stderr)
            time.sleep(2 ** attempt * 3)


def _slim(node):
    """Keep only what triage needs, in plain JSON."""
    author = node["author"] or {}
    return {
        "number": node["number"],
        "title": node["title"],
        "body": (node["body"] or "")[:BODY_LIMIT],
        "url": node["url"],
        "created_at": node["createdAt"],
        "updated_at": node["updatedAt"],
        "author": author.get("login") or "ghost",
        "author_is_bot": author.get("__typename") == "Bot",
        "author_association": node["authorAssociation"],
        "labels": [l["name"] for l in node["labels"]["nodes"]],
        "comment_count": node["comments"]["totalCount"],
        "comments": [
            {"created_at": c["createdAt"],
             "author": (c["author"] or {}).get("login") or "ghost",
             "author_is_bot": (c["author"] or {}).get("__typename") == "Bot",
             "author_association": c["authorAssociation"]}
            for c in node["comments"]["nodes"]
        ],
    }


MERGERS = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: MERGED, first: 100, after: $cursor,
                 orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { mergedBy { login } }
    }
  }
}
"""


def fetch_maintainers(repo, pages=3):
    """Logins that merged any of the last `pages`*100 merged pull requests.

    GitHub hides org membership from outsiders, so comment associations come
    back as NONE even for staff. Who can merge is public and is a good proxy
    for who speaks for the project.
    """
    owner, name = repo.split("/", 1)
    tok, cursor, who = token(), None, set()
    for _ in range(pages):
        page = _post({"query": MERGERS, "variables":
                      {"owner": owner, "name": name, "cursor": cursor}}, tok)["repository"]["pullRequests"]
        who |= {n["mergedBy"]["login"] for n in page["nodes"] if n["mergedBy"]}
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return sorted(who)


def fetch_open_issues(repo, limit=None, progress=True):
    owner, name = repo.split("/", 1)
    tok = token()
    issues, cursor, total = [], None, None
    while True:
        data = _post({"query": QUERY, "variables":
                      {"owner": owner, "name": name, "cursor": cursor}}, tok)
        page = data["repository"]["issues"]
        total = page["totalCount"]
        issues.extend(_slim(n) for n in page["nodes"])
        if progress:
            print(f"  fetched {len(issues)}/{total}", file=sys.stderr)
        if not page["pageInfo"]["hasNextPage"] or (limit and len(issues) >= limit):
            break
        cursor = page["pageInfo"]["endCursor"]
    return {"repo": repo, "total_open": total,
            "maintainers": fetch_maintainers(repo),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "issues": issues[:limit] if limit else issues}
