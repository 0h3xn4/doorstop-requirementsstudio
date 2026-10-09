"""Build the offline user guide: docs/guide/*.md -> src/rvs_core/guide/guide.html (one self-contained page).

Run after editing the guide:  python scripts/build_guide.py   (tests/test_guide.py checks the committed copy is current)
The output has no timestamp, script or link to anything outside the file, so it is reproducible and works offline.
"""

import html
import re
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
GUIDE_DIR = ROOT / "docs" / "guide"
OUTPUT = ROOT / "src" / "rvs_core" / "guide" / "guide.html"
SHORTCUTS_MARKER = "<!-- shortcuts-table -->"

# Layout only: colours come from the viewer so the guide follows the light or dark theme.
CSS = """
body { font-family: 'IBM Plex Sans', sans-serif; font-size: 11pt; margin: 12px 24px; }
h1 { font-size: 22pt; margin-top: 28px; }
h2 { font-size: 16pt; margin-top: 20px; }
h3 { font-size: 13pt; }
code { font-family: 'IBM Plex Mono', monospace; }
pre { font-family: 'IBM Plex Mono', monospace; padding: 8px; }
table { border-collapse: collapse; }
th { text-align: left; padding: 4px 8px; }
td { padding: 4px 8px; }
.toc li { margin-bottom: 2px; }
"""


def shortcuts_table() -> str:
    from rvs_gui.shortcuts import SHORTCUTS

    rows = ["| Shortcut | Action |", "|---|---|"]
    rows += [f"| **{key}** | {description} |" for key, description in SHORTCUTS.values()]
    return "\n".join(rows)


def _toc(tokens: list[dict[str, object]], depth: int = 0) -> str:
    items = []
    for t in tokens:
        children = t.get("children") or []
        sub = _toc(children, depth + 1) if children and depth < 1 else ""  # type: ignore[arg-type]
        items.append(f'<li><a href="#{t["id"]}">{t["name"]}</a>{sub}</li>')
    return "<ul>" + "".join(items) + "</ul>"


def build(guide_dir: Path = GUIDE_DIR) -> str:
    sources = sorted(guide_dir.glob("*.md"))
    text = "\n\n".join(p.read_text(encoding="utf-8").strip() for p in sources)
    text = text.replace(SHORTCUTS_MARKER, shortcuts_table())
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "sane_lists"], extension_configs={"toc": {"toc_depth": "1-2"}}
    )
    body = md.convert(text)
    # Qt's rich text scrolls to <a name>; keep the id attribute for other readers.
    body = re.sub(r'<(h[1-3]) id="([^"]+)">', r'<a name="\2"></a><\1 id="\2">', body)
    toc = _toc(md.toc_tokens)  # type: ignore[attr-defined]
    title = "Requirements & Verification Studio: user guide"
    return (
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>\n"
        f'<div class="toc"><h2>Contents</h2>{toc}</div>\n{body}\n</body></html>\n'
    )


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build(), encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
