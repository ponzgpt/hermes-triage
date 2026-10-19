"""Group likely duplicate issues.

TF-IDF over the title (weighted x3) and the code identifiers in the body head
(function names, config keys, error classes), cosine similarity, then
union-find into clusters. An inverted index keeps it to candidate pairs that
share rare terms, so 16k issues take seconds rather than 128M comparisons.
These are *candidates* for a human to confirm, never auto-closed.
"""

import math
import re
from collections import Counter, defaultdict

STOP = set("""
a an and are as at be but by can do does for from has have how i if in into is it its
not of on or so that the this to was when where which while with without bug feature
fr hermes agent issue error fails failed failing work works working doesn t don isn
wont won use using used should would could new also after before via only all no
""".split())

TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_./-]{2,}")
CODEY = re.compile(r"`([^`\n]{3,60})`|\b([a-z]+_[a-z0-9_]+|[A-Z][a-z]+[A-Z]\w+(?:Error|Exception))\b")


def _tokens(text):
    return [t.lower().strip("./-") for t in TOKEN.findall(text)
            if t.lower() not in STOP and not t.isdigit()]


def features(issue):
    title = re.sub(r"^\[[^\]]+\]:?\s*", "", issue["title"])
    feats = Counter()
    for t in _tokens(title):
        feats[t] += 3
    for m in CODEY.finditer(issue["body"][:1500]):
        for t in _tokens(m.group(1) or m.group(2)):
            feats[t] += 1
    return feats


class _DSU:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def clusters(issues, threshold=0.55, max_df=0.02):
    """List of clusters (lists of issue numbers, newest first), largest first.

    `max_df`: terms in more than this share of issues are too common to
    propose a pair on their own (they still count towards similarity).
    """
    n = len(issues)
    feats = {i["number"]: features(i) for i in issues}
    df = Counter(t for f in feats.values() for t in f)
    idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}
    vec = {}
    for num, f in feats.items():
        v = {t: w * idf[t] for t, w in f.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vec[num] = {t: x / norm for t, x in v.items()}

    cap = max(2, int(max_df * n))
    index = defaultdict(list)
    for num, f in feats.items():
        for t in f:
            if df[t] <= cap:
                index[t].append(num)

    dsu, pairs = _DSU(), {}
    for num in vec:
        shared = Counter(o for t in feats[num] if df[t] <= cap for o in index[t] if o < num)
        for other, k in shared.items():
            if k < 2:
                continue
            a, b = vec[num], vec[other]
            sim = sum(x * b.get(t, 0.0) for t, x in a.items())
            if sim >= threshold:
                dsu.union(num, other)
                pairs[(other, num)] = sim

    groups = defaultdict(list)
    for num in dsu.p:
        groups[dsu.find(num)].append(num)
    out = [sorted(g, reverse=True) for g in groups.values() if len(g) > 1]
    out.sort(key=lambda g: (-len(g), -g[0]))
    return out, pairs


def is_series(group, by_num, days=3):
    """True when one author filed (nearly) all of a cluster within a few days.

    Batch-filed work items ("Shard X", "Discord A1..A6") look alike on purpose;
    they are a plan, not duplicates, and the report lists them apart.
    """
    from collections import Counter
    from .metrics import ts
    authors = Counter(by_num[n]["author"] for n in group)
    _, top = authors.most_common(1)[0]
    times = sorted(ts(by_num[n]["created_at"]) for n in group)
    return top / len(group) >= 0.8 and (times[-1] - times[0]).days <= days
