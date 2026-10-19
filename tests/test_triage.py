import unittest
from datetime import datetime, timezone

from hermes_triage import classify, dupes, metrics
from hermes_triage.report import render


def issue(number, title, body="", labels=(), created="2026-10-01T00:00:00Z", author="alice", comments=()):
    return {"number": number, "title": title, "body": body, "labels": list(labels),
            "url": f"https://example.test/{number}", "created_at": created, "updated_at": created,
            "author": author, "author_is_bot": False, "author_association": "NONE",
            "comment_count": len(comments), "comments": list(comments)}


def comment(author, created, bot=False, assoc="NONE"):
    return {"author": author, "created_at": created, "author_is_bot": bot, "author_association": assoc}


class Classify(unittest.TestCase):
    def test_issue_form_component_wins_and_is_explained(self):
        body = "### Affected Component\n\nGateway (Telegram/Discord/Slack/WhatsApp)\n\n### Messaging Platform (if gateway-related)\n\nTelegram\n"
        got = classify.suggest_labels(issue(1, "[Bug]: replies stop", body))
        self.assertEqual(got["comp/gateway"], "issue form: Affected Component")
        self.assertEqual(got["platform/telegram"], "issue form: Messaging Platform")
        self.assertIn("type/bug", got)

    def test_maintainer_priority_beats_rules(self):
        self.assertEqual(classify.suggest_severity(issue(1, "deletes all messages", labels=["P3"])),
                         ("P3", "maintainer label"))

    def test_strong_signals_only_for_p1(self):
        self.assertEqual(classify.suggest_severity(issue(1, "Email channel wipes the mailbox"))[0], "P1")
        # "security" on its own (e.g. a CSP header) is not enough.
        self.assertEqual(classify.suggest_severity(issue(2, "[Bug]: frames stay small with a strict security policy"))[0], "P2")
        self.assertEqual(classify.suggest_severity(issue(3, "[Feature]: dark mode"))[0], "P3")

    def test_one_component_per_issue(self):
        got = classify.suggest_labels(issue(1, "gateway drops cron output", "the gateway restarts and the gateway log shows cron"))
        self.assertEqual([l for l in got if l.startswith("comp/")], ["comp/gateway"])

    def test_feature_request_is_never_p1(self):
        self.assertNotEqual(classify.suggest_severity(issue(1, "Feature: vulnerability scanning skill"))[0], "P1")

    def test_evaluate_ignores_issues_without_the_family(self):
        xs = [issue(1, "telegram drops photos", labels=["platform/telegram"]),
              issue(2, "telegram drops photos")]  # unlabelled: must not count as a false positive
        self.assertEqual(classify.evaluate(xs, families=("platform/",))["platform/"]["precision"], 1.0)


class Dupes(unittest.TestCase):
    def test_same_bug_clusters_and_unrelated_does_not(self):
        xs = [issue(1, "[Bug]: _enforce_minimum_context passes when ollama_window is smaller"),
              issue(2, "_enforce_minimum_context check passes with smaller ollama_window"),
              issue(3, "[Feature]: dark mode for the desktop app")]
        groups, _ = dupes.clusters(xs, max_df=1.0)
        self.assertEqual(groups, [[2, 1]])


    def test_batch_filed_series_is_not_a_duplicate(self):
        by_num = {n: issue(n, "x", created=f"2026-10-0{n}T00:00:00Z", author="planner") for n in (1, 2, 3)}
        self.assertTrue(dupes.is_series([3, 2, 1], by_num))
        by_num[2]["author"], by_num[3]["author"] = "bob", "carol"
        self.assertFalse(dupes.is_series([3, 2, 1], by_num))


class Metrics(unittest.TestCase):
    def test_first_response_skips_author_bots_and_non_maintainers(self):
        i = issue(1, "x", created="2026-10-01T00:00:00Z", comments=[
            comment("alice", "2026-10-01T01:00:00Z"),            # the author
            comment("ci-bot", "2026-10-01T02:00:00Z", bot=True),  # a bot
            comment("bob", "2026-10-01T03:00:00Z"),               # a user
            comment("teknium1", "2026-10-01T05:00:00Z")])         # a maintainer
        self.assertEqual(metrics.hours_to_first_response(i), 3)
        self.assertEqual(metrics.hours_to_first_response(i, {"teknium1"}), 5)
        self.assertIsNone(metrics.hours_to_first_response(issue(2, "y"), {"teknium1"}))


class Report(unittest.TestCase):
    def test_renders_every_section(self):
        snap = {"repo": "o/r", "total_open": 2, "fetched_at": "2026-10-19T00:00:00Z", "maintainers": ["m"],
                "issues": [issue(1, "[Bug]: cli crashes", "## Steps to Reproduce\n1. run hermes chat"),
                           issue(2, "[Feature]: telegram stickers", labels=["platform/telegram"])]}
        md = render(snap, now=datetime(2026, 10, 19, tzinfo=timezone.utc))
        for h in ("## Headline", "## By component", "## Likely duplicates", "## Good reproduction candidates",
                  "## How far to trust the suggestions", "## Method and limits"):
            self.assertIn(h, md)
        self.assertIn("[#1]", md.split("## Good reproduction candidates")[1])


if __name__ == "__main__":
    unittest.main()
