"""Queue-health numbers: response, age, labelling.

"Response" means the first comment by someone other than the issue's author
that is not a bot. "Maintainer response" further requires the commenter to be
someone who merges pull requests (see github.fetch_maintainers), or to carry
GitHub's OWNER/MEMBER/COLLABORATOR association. Only the first 10 comments of each
issue are fetched, which is enough to find the first response on all but a
handful of very long threads.
"""

from datetime import datetime

MAINTAINER = {"OWNER", "MEMBER", "COLLABORATOR"}


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def first_response(issue, maintainers=None):
    """Datetime of the first qualifying response, or None.

    `maintainers`: a set of logins; when given, only their comments (or ones
    with a maintainer association) count.
    """
    for c in issue["comments"]:
        if c["author_is_bot"] or c["author"] == issue["author"]:
            continue
        if maintainers is not None and c["author"] not in maintainers \
                and c["author_association"] not in MAINTAINER:
            continue
        return ts(c["created_at"])
    return None


def hours_to_first_response(issue, maintainers=None):
    r = first_response(issue, maintainers)
    return None if r is None else (r - ts(issue["created_at"])).total_seconds() / 3600


def quantile(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def age_days(issue, now):
    return (now - ts(issue["created_at"])).total_seconds() / 86400


AGE_BUCKETS = [(1, "< 1 day"), (7, "1–7 days"), (30, "8–30 days"), (90, "31–90 days"), (float("inf"), "> 90 days")]


def age_bucket(days):
    for limit, name in AGE_BUCKETS:
        if days < limit:
            return name
