#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MKDOCS_YML = ROOT / "mkdocs.yml"


def title_case_week(stem: str) -> str:
    """Convert 'week-01' -> 'Week 01'."""
    m = re.match(r"week-(\d+)$", stem)
    if not m:
        return stem
    return f"Week {m.group(1)}"


def guess_title_from_h1(md_path: Path) -> str | None:
    """Parse the first Markdown H1 line: '# Title'."""
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return None


def collect_weeks() -> list[tuple[int, str, str]]:
    """Returns list of (week_number, nav_label, rel_path)."""
    weeks_dir = DOCS / "weeks"
    if not weeks_dir.exists():
        return []

    items: list[tuple[int, str, str]] = []
    for p in weeks_dir.glob("week-*.md"):
        m = re.match(r"week-(\d+)\.md$", p.name)
        if not m:
            continue

        num = int(m.group(1))
        # Keep labels stable as "Week NN" (avoids overly long nav labels)
        label = title_case_week(p.stem)

        rel = p.relative_to(DOCS).as_posix()
        items.append((num, label, rel))

    items.sort(key=lambda x: x[0])
    return items


def collect_concepts() -> list[tuple[str, str]]:
    """Returns list of (nav_label, rel_path)."""
    concepts_dir = DOCS / "concepts"
    if not concepts_dir.exists():
        return []

    items: list[tuple[str, str]] = []
    for p in concepts_dir.glob("*.md"):
        # Skip concepts/index.md if you use it as an overview page; include it if you want.
        if p.name.lower() == "index.md":
            continue

        h1 = guess_title_from_h1(p)
        label = h1 if h1 else p.stem.replace("-", " ").replace("_", " ")

        rel = p.relative_to(DOCS).as_posix()
        items.append((label, rel))

    items.sort(key=lambda x: x[0].lower())
    return items


def render_full_nav_yaml() -> str:
    """
    Render a complete top-level 'nav:' block in YAML.
    Output is valid YAML with Weeks/Concepts at the same level as Home.
    """
    weeks = collect_weeks()
    concepts = collect_concepts()

    lines: list[str] = []
    lines.append("nav:")
    lines.append("  - Home: index.md")

    if weeks:
        lines.append("  - Weeks:")
        for _, label, rel in weeks:
            lines.append(f"      - {label}: {rel}")

    if concepts:
        lines.append("  - Concepts:")
        for label, rel in concepts:
            lines.append(f"      - {label}: {rel}")

    return "\n".join(lines) + "\n"


def replace_or_insert_nav_section(mkdocs_text: str, new_nav_yaml: str) -> str:
    """
    Replace existing top-level nav: block (if present), otherwise insert one.

    This pattern replaces:
      nav:
        <any number of indented lines>

    It stops replacement when indentation returns to column 0 (next top-level key).
    """
    # Normalize new nav string
    if not new_nav_yaml.endswith("\n"):
        new_nav_yaml += "\n"

    # Match a top-level nav block: "nav:" at col 0 + following indented lines
    nav_block_pattern = re.compile(
        r"^nav:\s*\r?\n"          # nav: line
        r"(?:^[ \t].*\r?\n)*",    # subsequent indented lines belonging to nav
        re.MULTILINE,
    )

    if nav_block_pattern.search(mkdocs_text):
        return nav_block_pattern.sub(new_nav_yaml, mkdocs_text, count=1)

    # If no nav exists, insert it in a sensible place: after plugins if present, else near top.
    # We try: after a top-level 'plugins:' block if it exists; otherwise after site_url if exists; otherwise at top.
    def insert_after_block(text: str, key: str) -> tuple[bool, str]:
        pat = re.compile(
            rf"^{re.escape(key)}:\s*\r?\n"      # key:
            r"(?:^[ \t].*\r?\n)*",              # its indented body (if any)
            re.MULTILINE,
        )
        m = pat.search(text)
        if not m:
            return False, text
        insert_pos = m.end()
        return True, text[:insert_pos] + "\n" + new_nav_yaml + "\n" + text[insert_pos:]

    inserted, mkdocs_text2 = insert_after_block(mkdocs_text, "plugins")
    if inserted:
        return mkdocs_text2

    # Insert after site_url line if present
    m = re.search(r"^site_url:.*\r?\n", mkdocs_text, flags=re.MULTILINE)
    if m:
        insert_pos = m.end()
        return mkdocs_text[:insert_pos] + "\n" + new_nav_yaml + "\n" + mkdocs_text[insert_pos:]

    # Fallback: prepend
    return new_nav_yaml + "\n" + mkdocs_text


def main() -> None:
    if not MKDOCS_YML.exists():
        raise SystemExit(f"mkdocs.yml not found at: {MKDOCS_YML}")

    mkdocs_text = MKDOCS_YML.read_text(encoding="utf-8", errors="replace")
    new_nav = render_full_nav_yaml()
    updated = replace_or_insert_nav_section(mkdocs_text, new_nav)
    MKDOCS_YML.write_text(updated, encoding="utf-8")
    print("Updated mkdocs.yml nav section.")


if __name__ == "__main__":
    main()
