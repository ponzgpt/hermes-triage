"""Turn the report's Markdown into one static HTML page.

ponytail: handles only the Markdown that report.py emits (headings, pipe
tables, one-level lists, blockquotes, links, `code`, **bold**, *italics*). If
the report grows other constructs, switch to a real Markdown library.
"""

import html
import re

CSS = """
:root{--bg:#fbfbf9;--fg:#141414;--muted:#5d5d5d;--rule:#d9d9d4;--accent:#1f4fd6}
@media (prefers-color-scheme:dark){:root{--bg:#111;--fg:#ececec;--muted:#a3a3a3;--rule:#333;--accent:#8fb0ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1040px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:1.7rem;margin:0 0 .4rem}h2{font-size:1.15rem;margin:2.2rem 0 .6rem;padding-top:.8rem;border-top:1px solid var(--rule)}
p,li{max-width:76ch}a{color:var(--accent)}code{font:.88em ui-monospace,Menlo,monospace}
blockquote{margin:1rem 0;padding:.4rem .9rem;border-left:3px solid var(--rule);color:var(--muted)}
.t{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{text-align:left;vertical-align:top;padding:.35rem .6rem;border-bottom:1px solid var(--rule)}
th{color:var(--muted);font-weight:600}ul{padding-left:1.2rem}li{margin:.15rem 0}
"""


def _inline(s):
    s = html.escape(s, quote=False).replace("\\|", "|")
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*([^*]+)\*(?!\w)", r"<em>\1</em>", s)
    return s


def _cells(row):
    return [c.strip() for c in re.split(r"(?<!\\)\|", row.strip().strip("|"))]


def to_html(md, title="Hermes Agent queue health"):
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# "):
            out.append(f"<h1>{_inline(ln[2:])}</h1>")
        elif ln.startswith("## "):
            out.append(f"<h2>{_inline(ln[3:])}</h2>")
        elif ln.startswith("|") and i + 1 < len(lines) and lines[i + 1].startswith("|---"):
            head = "".join(f"<th>{_inline(c)}</th>" for c in _cells(ln))
            i += 2
            body = []
            while i < len(lines) and lines[i].startswith("|"):
                body.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in _cells(lines[i])) + "</tr>")
                i += 1
            out.append(f'<div class="t"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')
            continue
        elif ln.startswith("- "):
            items = []
            while i < len(lines) and (lines[i].startswith("- ") or lines[i].startswith("  - ")):
                if lines[i].startswith("- "):
                    items.append([_inline(lines[i][2:]), []])
                else:
                    items[-1][1].append(_inline(lines[i][4:]))
                i += 1
            out.append("<ul>" + "".join(
                f"<li>{t}" + (f"<ul>{''.join(f'<li>{s}</li>' for s in sub)}</ul>" if sub else "") + "</li>"
                for t, sub in items) + "</ul>")
            continue
        elif ln.startswith("> "):
            out.append(f"<blockquote>{_inline(ln[2:])}</blockquote>")
        elif ln.strip():
            out.append(f"<p>{_inline(ln)}</p>")
        i += 1
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
            f"<body><main>{''.join(out)}</main></body></html>\n")
