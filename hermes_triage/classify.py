"""Suggest labels for an issue using the repository's own taxonomy.

Rules are plain regular expressions over the title and the first part of the
body, so every suggestion can be explained ("matched `telegram`"). They are not
meant to replace a maintainer; `evaluate()` measures how often they agree with
the labels maintainers already applied, and the report prints that number.
"""

import re

# label -> patterns. Matched case-insensitively against title + body head.
# Only labels that already exist in NousResearch/hermes-agent are used.
RULES = {
    # what kind of issue
    "type/bug": [r"^\[bug\]", r"\btraceback\b", r"\b(crash|crashes|crashed|error|exception|broken|fails?|failing)\b"],
    "type/feature": [r"^\[(feature|fr)\]", r"\b(feature request|would be nice|add support for|option to)\b"],
    "type/security": [r"\b(security|vulnerab|cve-\d|secret leak|token leak|exfiltrat|injection|sandbox escape)\b"],
    "type/perf": [r"\b(slow|latency|cpu|memory leak|saturat|high memory|performance)\b"],
    # component
    "comp/gateway": [r"\bgateway\b"],
    "comp/cli": [r"\bcli\b", r"\bhermes (chat|setup|doctor|update|model)\b"],
    "comp/desktop": [r"\bdesktop\b", r"\belectron\b"],
    "comp/tui": [r"\btui\b"],
    "comp/cron": [r"\bcron\b", r"\bscheduled (job|task)s?\b"],
    "comp/plugins": [r"\bplugins?\b"],
    "comp/tools": [r"\btool[- ]?(call|use|loop)\b", r"\b(terminal|file|web|browser) tool\b"],
    "comp/dashboard": [r"\bdashboard\b"],
    "comp/acp": [r"\bacp\b"],
    # area
    "area/install-update": [r"\b(install|installer|install\.sh|hermes update|upgrade|uninstall)\b", r"^\[setup\]"],
    "area/config": [r"\bconfig(\.yaml)?\b", r"\.env\b"],
    "area/auth": [r"\b(oauth|auth|login|api key|credential)s?\b"],
    "area/sessions": [r"\bsessions?\b"],
    "area/profiles": [r"\bprofiles?\b"],
    "area/compression": [r"\b(compaction|compression|compress|context window)\b"],
    "area/streaming": [r"\bstream(ing|ed)?\b"],
    "area/local-models": [r"\b(ollama|llama\.cpp|lm studio|vllm|gguf|local model)\b"],
    "area/i18n": [r"\b(i18n|translation|locale|unicode)\b"],
    # tools
    "tool/mcp": [r"\bmcp\b"],
    "tool/skills": [r"\bskills?\b"],
    "tool/memory": [r"\bmemory tool\b", r"\bmemor(y|ies)\b"],
    "tool/browser": [r"\bbrowser\b"],
    "tool/terminal": [r"\bterminal\b"],
    # platform
    "platform/telegram": [r"\btelegram\b"],
    "platform/discord": [r"\bdiscord\b"],
    "platform/slack": [r"\bslack\b"],
    "platform/whatsapp": [r"\bwhatsapp\b"],
    "platform/signal": [r"\bsignal\b(?! handler)"],
    "platform/matrix": [r"\bmatrix\b"],
    "platform/email": [r"\b(email|imap|smtp)\b"],
    # provider
    "provider/anthropic": [r"\b(anthropic|claude)\b"],
    "provider/openai": [r"\b(openai|gpt-\d|codex)\b"],
    "provider/openrouter": [r"\bopenrouter\b"],
    "provider/ollama": [r"\bollama\b"],
    "provider/gemini": [r"\bgemini\b"],
    "provider/deepseek": [r"\bdeepseek\b"],
    "provider/nous": [r"\bnous portal\b", r"\bportal\.nousresearch"],
    # os
    "os/windows": [r"\bwindows\b", r"\bpowershell\b", r"\bwsl\b"],
    "os/macos": [r"\bmacos\b", r"\bos x\b", r"\bdarwin\b"],
}

# The bug template's "Affected Component" dropdown maps straight onto labels.
TEMPLATE_COMPONENT = {
    "CLI (interactive chat)": "comp/cli",
    "Gateway (Telegram/Discord/Slack/WhatsApp)": "comp/gateway",
    "Setup / Installation": "area/install-update",
    "Tools (terminal, file ops, web, code execution, etc.)": "comp/tools",
    "Skills (skill loading, skill hub, skill guard)": "tool/skills",
    "Agent Core (conversation loop, context compression, memory)": "comp/agent",
    "Configuration (config.yaml, .env, hermes setup)": "area/config",
}
TEMPLATE_PLATFORM = {p: f"platform/{p.lower()}" for p in ("Telegram", "Discord", "Slack", "WhatsApp")}

# Severity, highest first. P0/P1 are only suggested on strong signals: a wrong
# "urgent" costs a maintainer more than a missed one costs the queue.
SEVERITY_RULES = [
    ("P1", [r"\b(data loss|lose[sd]? (data|messages|history)|wipes?|deletes? (all|every)|corrupt)",
            r"\b(security (hole|issue|bug|vulnerability)|vulnerab|leak(s|ed)? (secret|token|key|credential)|exfiltrat|sandbox escape|cve-\d)",
            r"\b(can'?t|cannot|unable to) (start|launch|install|log ?in)\b",
            r"\b(restart loop|crash loop|boot loop)\b"]),
    ("P2", [r"^\[bug\]", r"\b(crash|traceback|exception|regression|silently|hangs?|stuck|fails?)\b"]),
    ("P3", [r"^\[(feature|fr)\]", r"\b(feature|enhancement|docs?|documentation|typo|cosmetic)\b"]),
]
PRIORITIES = ("P0", "P1", "P2", "P3", "P4")

HEAD = 1500  # characters of body that rules look at


def _compile(rules):
    return {k: [re.compile(p, re.I | re.M) for p in v] for k, v in rules.items()}


_RULES = _compile(RULES)
_SEVERITY = [(lvl, [re.compile(p, re.I | re.M) for p in pats]) for lvl, pats in SEVERITY_RULES]


def text_of(issue):
    return f"{issue['title']}\n{issue['body'][:HEAD]}"


def template_field(body, heading):
    """Value under a `### <heading>` block written by a GitHub issue form."""
    m = re.search(rf"^###\s+{re.escape(heading)}\s*\n+(.+?)\s*$", body, re.M)
    return m.group(1).strip() if m else None


def suggest_labels(issue):
    """Return {label: reason} for labels the rules would apply."""
    text = text_of(issue)
    out = {}
    comp = template_field(issue["body"], "Affected Component")
    if comp in TEMPLATE_COMPONENT:
        out[TEMPLATE_COMPONENT[comp]] = "issue form: Affected Component"
    plat = template_field(issue["body"], "Messaging Platform (if gateway-related)")
    if plat in TEMPLATE_PLATFORM:
        out[TEMPLATE_PLATFORM[plat]] = "issue form: Messaging Platform"
    comp_hits = {}
    for label, pats in _RULES.items():
        if label in out:
            continue
        hits = [m for p in pats for m in p.finditer(text)]
        if not hits:
            continue
        if label.startswith("comp/"):
            comp_hits[label] = hits
        else:
            out[label] = f"matched `{hits[0].group(0).strip()}`"
    # One component per issue, as maintainers label: the issue form if it
    # answered, otherwise the component named most often (title counts double).
    if comp_hits and not any(l.startswith("comp/") for l in out):
        title_end = len(issue["title"])
        def score(item):
            return sum(2 if m.start() < title_end else 1 for m in item[1])
        best, hits = max(comp_hits.items(), key=score)
        out[best] = f"matched `{hits[0].group(0).strip()}`"
    return out


def suggest_severity(issue):
    """(priority, reason). Existing P-labels win; otherwise rules; default P3."""
    for lvl in PRIORITIES:
        if lvl in issue["labels"]:
            return lvl, "maintainer label"
    text = text_of(issue)
    feature = re.search(r"^\[?(feature|fr|feat)\b", issue["title"], re.I) or "type/feature" in issue["labels"] \
        or "enhancement" in issue["labels"]
    for lvl, pats in _SEVERITY:
        if feature and lvl == "P1":
            continue  # a request for a security feature is not a security incident
        for p in pats:
            m = p.search(text)
            if m:
                return lvl, f"matched `{m.group(0).strip()}`"
    return "P3", "default"


def evaluate(issues, families=("comp/", "platform/", "provider/", "os/", "type/")):
    """Agreement with maintainer labels on issues that already carry them.

    For each label family, precision = suggested labels that maintainers also
    applied / all suggested; recall = maintainer labels the rules also found /
    all maintainer labels. Only issues with at least one label in the family
    count, so an unlabelled issue never penalises the rules.
    """
    stats = {}
    for fam in families:
        tp = fp = fn = 0
        for i in issues:
            truth = {l for l in i["labels"] if l.startswith(fam)}
            if not truth:
                continue
            guess = {l for l in suggest_labels(i) if l.startswith(fam)}
            tp += len(guess & truth)
            fp += len(guess - truth)
            fn += len(truth - guess)
        if tp + fp + fn:
            stats[fam] = {
                "precision": tp / (tp + fp) if tp + fp else 0.0,
                "recall": tp / (tp + fn) if tp + fn else 0.0,
                "issues": sum(1 for i in issues if any(l.startswith(fam) for l in i["labels"])),
            }
    return stats
