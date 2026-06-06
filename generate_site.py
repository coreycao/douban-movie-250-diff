"""
Generate a static GitHub Pages site for Douban Movie 250 Diff.

Reads recently_movie_250.json, README.md, and archive/*.md
to produce a Douban-styled website in _site/.
"""

import glob
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ChangeEntry:
    name: str
    link: str
    movie_id: str
    rank_display: str = ""
    score_display: str = ""
    rank_class: str = ""  # "rank-up", "rank-down", "rank-same"


@dataclass
class DailyDiff:
    date: str = ""
    total_changes: int = 0
    rank_changes: int = 0
    score_changes: int = 0
    new_count: int = 0
    removed_count: int = 0
    new_entries: list = field(default_factory=list)       # list[ChangeEntry]
    removed_entries: list = field(default_factory=list)    # list[ChangeEntry]
    changes: list = field(default_factory=list)            # list[ChangeEntry]


@dataclass
class ArchiveMonth:
    filename: str = ""        # e.g. "2026-05"
    filename_ext: str = ""    # e.g. "2026-05.md"
    month_label: str = ""     # e.g. "2026年5月"
    first_date: str = ""
    last_date: str = ""
    entry_count: int = 0
    diffs: list = field(default_factory=list)  # list[DailyDiff]


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

_RE_DATE = re.compile(r'^## (\d{4}-\d{2}-\d{2})')
_RE_STAT = re.compile(r'- \*\*(.+?)\*\*:\s*(\d+)')
_RE_LINK = re.compile(r'\[([^\]]+)\]\(https?://movie\.douban\.com/subject/(\d+)/?\)')
_RE_NEW_RANK = re.compile(r'(↑|↓)\s*(\d+)→(\d+)\s*\(([+-]?\d+)\)')
_RE_OLD_RANK = re.compile(r'(\d+)\s*➡️\s*(\d+)')
_RE_NEW_SCORE = re.compile(r'(↑|↓)\s*([\d.]+)→([\d.]+)\s*\(([+-]?[\d.]+)\)')
_RE_ARCHIVE_META = re.compile(r'^<!--\s*(\w[\w\s]*?):\s*(.+?)\s*-->$')


def parse_markdown_diffs(filepath: str) -> list[DailyDiff]:
    """Parse a markdown file into a list of DailyDiff objects."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    diffs: list[DailyDiff] = []
    current: DailyDiff | None = None
    section = ""  # "", "stats", "new", "removed", "changes"

    for line in lines:
        m = _RE_DATE.match(line)
        if m:
            if current:
                diffs.append(current)
            current = DailyDiff(date=m.group(1))
            section = "stats"
            continue

        if current is None:
            continue

        # Stats
        if section == "stats":
            sm = _RE_STAT.match(line.strip())
            if sm:
                key, val = sm.group(1), int(sm.group(2))
                if '总变更' in key:
                    current.total_changes = val
                elif '排名变化' in key:
                    current.rank_changes = val
                elif '评分变化' in key:
                    current.score_changes = val
                elif '新上榜' in key:
                    current.new_count = val
                elif '退出榜单' in key:
                    current.removed_count = val

        # Section headers
        if '新上榜' in line and line.startswith('####'):
            section = "new"
            continue
        if '退出榜单' in line and line.startswith('####'):
            section = "removed"
            continue
        if ('排名及分数变化' in line or '变化' in line) and line.startswith('####'):
            section = "changes"
            continue

        # Table rows
        if line.startswith('|') and '[' in line:
            entry = _parse_table_row(line)
            if entry is None:
                continue
            if section == "new":
                current.new_entries.append(entry)
            elif section == "removed":
                current.removed_entries.append(entry)
            elif section == "changes":
                current.changes.append(entry)

    if current:
        diffs.append(current)

    return diffs


def _parse_table_row(line: str) -> ChangeEntry | None:
    """Parse a single markdown table row into a ChangeEntry."""
    lm = _RE_LINK.search(line)
    if not lm:
        return None

    name = lm.group(1)
    movie_id = lm.group(2)
    link = f"https://movie.douban.com/subject/{movie_id}/"

    cells = [c.strip() for c in line.split('|')]
    # cells: ['', name-cell, rank-cell, score-cell, ''] or ['', rank, name, score, '']
    # Detect layout by checking which cell has the link
    link_cell_idx = None
    for i, c in enumerate(cells):
        if movie_id in c:
            link_cell_idx = i
            break
    if link_cell_idx is None:
        return None

    # For new/removed tables: | rank | [name](link) | score |
    # For changes table:       | [name](link) | rank | score |
    rank_cell = ""
    score_cell = ""
    rank_class = ""

    if link_cell_idx == 2:
        # Layout: | rank | name | score |
        rank_cell = cells[1] if len(cells) > 1 else ""
        score_cell = cells[3] if len(cells) > 3 else ""
    elif link_cell_idx == 1:
        # Layout: | name | rank | score |
        rank_cell = cells[2] if len(cells) > 2 else ""
        score_cell = cells[3] if len(cells) > 3 else ""
    else:
        rank_cell = cells[link_cell_idx + 1] if len(cells) > link_cell_idx + 1 else ""
        score_cell = cells[link_cell_idx + 2] if len(cells) > link_cell_idx + 2 else ""

    # Parse rank display
    rank_display, rank_class = _parse_rank_cell(rank_cell)
    score_display = _parse_score_cell(score_cell)

    return ChangeEntry(
        name=escape(name),
        link=link,
        movie_id=movie_id,
        rank_display=rank_display,
        score_display=score_display,
        rank_class=rank_class,
    )


def _parse_rank_cell(cell: str) -> tuple[str, str]:
    """Return (display_html, css_class) for a rank cell."""
    cell = cell.strip()
    if not cell or cell == '—':
        return '—', 'rank-same'

    # New format: ↑ 189→188 (+1)
    m = _RE_NEW_RANK.search(cell)
    if m:
        direction = m.group(1)
        old_rank = m.group(2)
        new_rank = m.group(3)
        delta = m.group(4)
        cls = 'rank-up' if direction == '↑' else 'rank-down'
        display = f'{direction} {escape(old_rank)}→{escape(new_rank)} ({escape(delta)})'
        return display, cls

    # Old format: 58 ➡️ 59
    m = _RE_OLD_RANK.search(cell)
    if m:
        old_rank = m.group(1)
        new_rank = m.group(2)
        try:
            diff = int(old_rank) - int(new_rank)
        except ValueError:
            diff = 0
        if diff > 0:
            return f'↑ {escape(old_rank)}→{escape(new_rank)} (+{diff})', 'rank-up'
        elif diff < 0:
            return f'↓ {escape(old_rank)}→{escape(new_rank)} ({diff})', 'rank-down'
        else:
            return f'{escape(old_rank)}→{escape(new_rank)}', 'rank-same'

    # Fallback: just show the cell content
    return escape(cell), ''


def _parse_score_cell(cell: str) -> str:
    """Return display HTML for a score cell."""
    cell = cell.strip()
    if not cell or cell == '—':
        return '—'

    m = _RE_NEW_SCORE.search(cell)
    if m:
        return escape(cell)

    # Old format: just a number like "9.2"
    try:
        float(cell)
        return escape(cell)
    except ValueError:
        return escape(cell)


def parse_archive_meta(filepath: str) -> dict:
    """Extract metadata from archive HTML comments."""
    meta = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line.startswith('<!--'):
                break
            m = _RE_ARCHIVE_META.match(line)
            if m:
                meta[m.group(1).strip()] = m.group(2).strip()
    return meta


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def _header(active: str = "home", base_path: str = "") -> str:
    """Render site header.

    base_path: "" for root pages, "../" for archive subdirectory pages.
    """
    nav_items = [
        ("home", "首页", f"{base_path}index.html"),
        ("archive", "历史归档", f"{base_path}archive/index.html"),
        ("github", "GitHub", "https://github.com/coreycao/douban-movie-250-diff"),
    ]
    nav_html = ""
    for key, label, href in nav_items:
        cls = ' class="active"' if key == active else ''
        nav_html += f'<a href="{href}"{cls}>{label}</a>\n'

    return f"""<header class="site-header">
  <div class="header-inner">
    <a href="{base_path}index.html" class="site-title">
      <span class="icon">豆</span>
      豆瓣 Top250 变化追踪
    </a>
    <nav class="site-nav">
      {nav_html}
    </nav>
    <button class="hamburger" aria-label="菜单" aria-expanded="false">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round">
        <line x1="3" y1="6" x2="21" y2="6"/>
        <line x1="3" y1="12" x2="21" y2="12"/>
        <line x1="3" y1="18" x2="21" y2="18"/>
      </svg>
    </button>
  </div>
</header>"""


def _footer() -> str:
    return """<footer class="site-footer">
  <p>豆瓣 Top250 变化追踪 · 数据每日自动更新 ·
    <a href="https://github.com/coreycao/douban-movie-250-diff">GitHub</a>
  </p>
</footer>"""


def _page_wrapper(title: str, header_active: str, body: str,
                   base_path: str = "") -> str:
    """Wrap body in full HTML page.

    base_path: "" for root pages, "../" for archive subdirectory pages.
    """
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(title)}</title>
  <link rel="stylesheet" href="{base_path}style.css">
</head>
<body>
{_header(header_active, base_path)}
<main class="container">
{body}
</main>
{_footer()}
<script src="{base_path}script.js"></script>
</body>
</html>"""


def _render_diff_card(diff: DailyDiff, collapsible: bool = False) -> str:
    """Render one day's diff as HTML."""
    stats_html = _render_stats(diff)
    new_html = _render_entry_section("🆕 新上榜电影", diff.new_entries, "new-entry")
    removed_html = _render_entry_section("❌ 退出榜单", diff.removed_entries, "removed-entry")
    changes_html = _render_changes_table(diff.changes)

    inner = f"""
    {stats_html}
    {new_html}
    {removed_html}
    {changes_html}"""

    if collapsible:
        return f"""<details class="diff-detail">
  <summary><span>{escape(diff.date)}</span></summary>
  <div class="detail-body">
    <div class="diff-card">
      {inner}
    </div>
  </div>
</details>"""
    else:
        return f"""<div class="diff-card">
  <div class="diff-date">
    {escape(diff.date)}
    <span class="date-badge">最新</span>
  </div>
  {inner}
</div>"""


def _render_stats(diff: DailyDiff) -> str:
    items = [
        (diff.total_changes, '总变更'),
        (diff.rank_changes, '排名变化'),
        (diff.score_changes, '评分变化'),
        (diff.new_count, '新上榜'),
        (diff.removed_count, '退出榜单'),
    ]
    cells = "\n".join(
        f'<div class="stat-item"><div class="stat-value">{v}</div><div class="stat-label">{label}</div></div>'
        for v, label in items
    )
    return f'<div class="stats-row">{cells}</div>'


def _render_entry_section(title: str, entries: list, css_class: str) -> str:
    if not entries:
        return ""

    rows = ""
    for e in entries:
        rows += f"""<tr>
      <td><a href="{e.link}" target="_blank" class="movie-link">{e.name}</a></td>
      <td>{e.rank_display}</td>
      <td>{e.score_display}</td>
    </tr>\n"""

    return f"""<h4 class="section-header {css_class}">{title}</h4>
<table class="change-table">
  <thead><tr><th>电影</th><th>排名</th><th>评分</th></tr></thead>
  <tbody>{rows}  </tbody>
</table>"""


def _render_changes_table(changes: list) -> str:
    if not changes:
        return ""

    rows = ""
    for e in changes:
        rows += f"""<tr>
      <td><a href="{e.link}" target="_blank" class="movie-link">{e.name}</a></td>
      <td class="{e.rank_class}">{e.rank_display}</td>
      <td class="score-badge">{e.score_display}</td>
    </tr>\n"""

    return f"""<h4 class="section-header">排名及分数变化</h4>
<table class="change-table">
  <thead><tr><th>电影</th><th>排名</th><th>评分</th></tr></thead>
  <tbody>{rows}  </tbody>
</table>"""


def _render_movie_grid(movies: list) -> str:
    """Render the Top 250 grid."""
    cards = ""
    for m in movies:
        rank = m.get('rank', '')
        name = escape(m.get('name', ''))
        link = m.get('link', '')
        score = m.get('score', '')
        pic = m.get('pic', '')

        try:
            rank_num = int(rank)
        except (ValueError, TypeError):
            rank_num = 999

        top_class = ' top-10' if rank_num <= 10 else ''

        cards += f"""<div class="movie-card">
  <div class="poster-wrap">
    <a href="{link}" target="_blank">
      <img src="{pic}" alt="{name}" loading="lazy" referrerpolicy="no-referrer"
           onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 200 300%22><rect fill=%22%23ddd%22 width=%22200%22 height=%22300%22/><text fill=%22%23999%22 x=%2250%25%22 y=%2250%25%22 dominant-baseline=%22middle%22 text-anchor=%22middle%22 font-size=%2216%22>暂无图片</text></svg>'">
    </a>
    <span class="rank-badge{top_class}">{rank}</span>
  </div>
  <div class="card-info">
    <div class="card-title"><a href="{link}" target="_blank">{name}</a></div>
    <div class="card-score">⭐ {score}</div>
  </div>
</div>\n"""

    return f"""<div class="section-title-bar">
  <h2 class="page-title" style="margin-bottom:0">当前 Top 250</h2>
</div>
<div class="movie-grid">
  {cards}
</div>"""


# ---------------------------------------------------------------------------
# Page renderers
# ---------------------------------------------------------------------------

def render_index(latest_diffs: list, movies: list, archive_months: list) -> str:
    """Render the home page."""
    # Latest diff
    diff_section = ""
    if latest_diffs:
        diff_section = f"""<div class="latest-section">
  <h2 class="page-title">最新变化</h2>
  {_render_diff_card(latest_diffs[0], collapsible=False)}
</div>"""
    else:
        diff_section = """<div class="empty-state">
  <div class="empty-icon">🎬</div>
  <p>暂无变化记录</p>
</div>"""

    # Recent history (if more diffs in README)
    history_section = ""
    if len(latest_diffs) > 1:
        history_items = ""
        for d in latest_diffs[1:]:
            history_items += _render_diff_card(d, collapsible=True)
        history_section = f"""<h2 class="page-title">近期变化</h2>
{history_items}"""

    # Top 250 grid
    movie_section = _render_movie_grid(movies)

    # Quick archive links
    archive_preview = ""
    if archive_months:
        cards = ""
        for am in archive_months[:6]:
            cards += f"""<a href="archive/{am.filename}.html" class="archive-card">
  <div class="archive-month">{am.month_label}</div>
  <div class="archive-count">{am.entry_count}</div>
  <div class="archive-count-label">次更新</div>
  <div class="archive-meta">{am.first_date} ~ {am.last_date}</div>
</a>\n"""
        archive_preview = f"""<h2 class="page-title">历史归档</h2>
<div class="archive-grid">
  {cards}
</div>
<p style="text-align:center;margin-top:16px">
  <a href="archive/index.html">查看全部归档 →</a>
</p>"""

    body = f"""{diff_section}
{history_section}
{movie_section}
{archive_preview}"""

    return _page_wrapper("豆瓣 Top250 变化追踪", "home", body)


def render_archive_index(archive_months: list) -> str:
    """Render the archive listing page."""
    if not archive_months:
        body = """<div class="empty-state">
  <div class="empty-icon">📂</div>
  <p>暂无归档记录</p>
</div>"""
        return _page_wrapper("历史归档", "archive", body, base_path="../")

    cards = ""
    for am in archive_months:
        cards += f"""<a href="{am.filename}.html" class="archive-card">
  <div class="archive-month">{am.month_label}</div>
  <div class="archive-count">{am.entry_count}</div>
  <div class="archive-count-label">次更新</div>
  <div class="archive-meta">{am.first_date} ~ {am.last_date}</div>
</a>\n"""

    body = f"""<h2 class="page-title">历史归档</h2>
<div class="archive-grid">
  {cards}
</div>"""

    return _page_wrapper("历史归档 - 豆瓣 Top250 变化追踪", "archive", body,
                         base_path="../")
def render_month_page(month: ArchiveMonth, prev_month: ArchiveMonth | None,
                      next_month: ArchiveMonth | None) -> str:
    """Render a monthly archive page."""
    # Navigation
    prev_link = f'<a href="{prev_month.filename}.html">← {prev_month.month_label}</a>' if prev_month else '<span></span>'
    next_link = f'<a href="{next_month.filename}.html">{next_month.month_label} →</a>' if next_month else '<span></span>'

    nav_html = f"""<div class="month-nav">
  {prev_link}
  <span class="month-label">{month.month_label}</span>
  {next_link}
</div>"""

    # Daily diffs
    diffs_html = ""
    for d in month.diffs:
        diffs_html += _render_diff_card(d, collapsible=True)

    body = f"""{nav_html}
{diffs_html}"""

    return _page_wrapper(f"{month.month_label} - 豆瓣 Top250 变化追踪", "archive", body,
                         base_path="../")


# ---------------------------------------------------------------------------
# Build orchestrator
# ---------------------------------------------------------------------------

def _month_label(month_str: str) -> str:
    """Convert '2026-05' or '2026-05-28' to '2026年5月'."""
    parts = month_str.split('-')
    if len(parts) >= 2:
        try:
            return f"{parts[0]}年{int(parts[1])}月"
        except (ValueError, IndexError):
            return month_str
    return month_str


def generate():
    """Generate the full static site."""
    base_dir = Path(__file__).parent
    site_dir = base_dir / '_site'
    assets_dir = base_dir / 'site_assets'
    archive_dir = base_dir / 'archive'

    # Clean output
    if site_dir.exists():
        shutil.rmtree(site_dir)
    os.makedirs(site_dir / 'archive', exist_ok=True)

    # 1. Load current movie list
    movies = []
    json_path = base_dir / 'recently_movie_250.json'
    if json_path.exists():
        with open(json_path, 'r', encoding='utf-8') as f:
            movies = json.load(f)
        print(f"Loaded {len(movies)} movies from recently_movie_250.json")

    # 2. Parse README.md for latest diff(s)
    readme_path = base_dir / 'README.md'
    latest_diffs = []
    if readme_path.exists():
        latest_diffs = parse_markdown_diffs(str(readme_path))
        # Deduplicate same-day entries
        seen_dates = set()
        deduped = []
        for d in latest_diffs:
            if d.date not in seen_dates:
                seen_dates.add(d.date)
                deduped.append(d)
        latest_diffs = deduped
        print(f"Parsed {len(latest_diffs)} diff entries from README.md")

    # 3. Discover and parse all archive files
    archive_months: list[ArchiveMonth] = []
    archive_files = sorted(glob.glob(str(archive_dir / '*.md')))
    for fpath in archive_files:
        fname = os.path.basename(fpath)
        if fname == 'INDEX.md':
            continue

        # Derive month key from filename
        stem = fname.replace('.md', '')
        # e.g. "2026-05" or "2025-03-03" → use first 7 chars for key
        month_key = stem[:7] if len(stem) >= 7 else stem

        meta = parse_archive_meta(fpath)
        diffs = parse_markdown_diffs(fpath)
        # Deduplicate
        seen = set()
        deduped = []
        for d in diffs:
            if d.date not in seen:
                seen.add(d.date)
                deduped.append(d)
        diffs = deduped

        first_date = meta.get('Date Range', '').split(' ~ ')[0] if 'Date Range' in meta else ''
        last_date = meta.get('Date Range', '').split(' ~ ')[-1] if 'Date Range' in meta else ''
        if not first_date and diffs:
            first_date = diffs[-1].date  # oldest (listed last in file)
            last_date = diffs[0].date    # newest (listed first)

        entry_count = int(meta.get('Total Entries', str(len(diffs))))

        archive_months.append(ArchiveMonth(
            filename=month_key,
            filename_ext=fname,
            month_label=_month_label(month_key),
            first_date=first_date,
            last_date=last_date,
            entry_count=entry_count or len(diffs),
            diffs=diffs,
        ))

    # Sort by month descending (newest first)
    archive_months.sort(key=lambda m: m.filename, reverse=True)
    print(f"Parsed {len(archive_months)} archive months")

    # 4. Copy static assets
    if assets_dir.exists():
        for asset in assets_dir.iterdir():
            shutil.copy2(str(asset), str(site_dir / asset.name))
    else:
        print("Warning: site_assets/ directory not found")

    # 5. Render pages
    # index.html
    index_html = render_index(latest_diffs, movies, archive_months)
    (site_dir / 'index.html').write_text(index_html, encoding='utf-8')
    print("Generated index.html")

    # archive/index.html
    archive_index_html = render_archive_index(archive_months)
    (site_dir / 'archive' / 'index.html').write_text(archive_index_html, encoding='utf-8')
    print("Generated archive/index.html")

    # archive/YYYY-MM.html
    for i, month in enumerate(archive_months):
        prev_month = archive_months[i + 1] if i + 1 < len(archive_months) else None
        next_month = archive_months[i - 1] if i > 0 else None
        month_html = render_month_page(month, prev_month, next_month)
        (site_dir / 'archive' / f'{month.filename}.html').write_text(month_html, encoding='utf-8')

    print(f"Generated {len(archive_months)} archive month pages")

    # Summary
    total_files = 2 + len(archive_months) + len(list(site_dir.glob('*.css'))) + len(list(site_dir.glob('*.js')))
    print(f"\nDone! Generated {total_files} files in _site/")


if __name__ == '__main__':
    generate()
