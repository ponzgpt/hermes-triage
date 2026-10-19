# hermes-triage

A read-only triage tool for the [Hermes Agent](https://github.com/NousResearch/hermes-agent) issue queue. It
takes a snapshot of every open issue and writes a Markdown report of the queue's health: who is waiting and for
how long, which issues are likely duplicates, which unlabelled issues belong where, and which bugs one person can
reproduce today.

**Latest report:** https://hermes-triage.technoir.cloud · [reports/](reports/)

Unofficial. Not affiliated with or endorsed by Nous Research. It never writes to GitHub: no labels, no comments,
no closes. It suggests, and a person decides.

## What the first run found (19 October 2026, 16,206 open issues)

- **41% have no reply from anyone but their author; 86% have none from a maintainer.** When a maintainer does
  reply, it is usually fast (median 16 minutes) or not at all (p90 36 days). Responses are bimodal, not slow.
- **One open issue in three is under 30 days old.** 5,152 opened in the last 30 days, and 57% of those are still
  unanswered.
- **227 clusters of likely duplicates covering 545 issues**, filed by different people over time. For example,
  seven separate reports of the same plugin-registration race ("dictionary changed size during iteration").
  Another 99 look-alike *series* (346 issues) were batch-filed by one author within three days. That is planned
  work, so the report lists those apart instead of calling them duplicates.
- **665 issues are labelled `duplicate` and still open.** That is the cheapest cleanup in the queue.
- **2,455 bugs have written reproduction steps, no maintainer reply, and sit in areas one person can reproduce
  locally.** The report lists the easiest first.

## Use

Python 3.10+, standard library only. The token comes from `GITHUB_TOKEN`, or from `gh auth token` if the GitHub
CLI is logged in. Read access is enough.

```bash
python3 -m hermes_triage.cli fetch                       # ~7 min for 16k issues → data/issues.json
python3 -m hermes_triage.cli report --out reports/$(date +%F).md --html site/index.html
```

`fetch --limit 500` takes the newest 500 for a quick look. `--repo OWNER/NAME` points it at another repository;
the label rules assume Hermes' taxonomy.

## How it decides

| Question | Method | How far to trust it |
|---|---|---|
| Has anyone answered? | First comment by someone other than the author that is not a bot. A *maintainer* is anyone who merged one of the last 300 merged PRs, because GitHub hides org membership from outsiders. | Exact, for the first 10 comments of each issue |
| Which component, platform, provider, OS? | The bug form's *Affected Component* field first, then plain regular expressions over the title and body, only ever proposing labels the repo already has. Maintainer labels always win. | Measured on every run against labels maintainers applied: on 19 Oct, `os/` 97% precision, `platform/` 71%, `comp/` 68%, `provider/` 56% |
| How urgent? | Existing `P0`–`P4` labels win. Otherwise P1 only on strong signals (data loss, a security leak, cannot start), never for a feature request. | Conservative on purpose: a false "urgent" costs a maintainer more than a missed one |
| Duplicates? | TF-IDF cosine over titles and code identifiers, an inverted index for speed, union-find into clusters. One author filing a batch within three days counts as a series, not a duplicate. | Candidates for a person to confirm |

Every suggestion in the report carries its reason ("matched `restart loop`", "issue form: Affected Component"),
so a maintainer can see why without reading the code.

## Check

```bash
./scripts/check.sh      # compile + unit tests; CI runs the same
```

## Authorship

I specified this tool, set its rules (read-only, the repo's own labels, explainable suggestions, measured
agreement) and reviewed its output against the live queue. An agent wrote most of the code.

MIT licence.
