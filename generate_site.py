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
from datetime import datetime
from html import escape
from pathlib import Path
from src.readme_renderer import DATE_HEADING_RE

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ChangeEntry:
    name: str
    link: str
    movie_id: str
    rank_old: str = ""
    rank_new: str = ""
    rank_delta: int | None = None
    score_old: str = ""
    score_new: str = ""
    score_delta: str = ""


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

_RE_DATE = DATE_HEADING_RE
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
    if link_cell_idx == 2:
        rank_cell = cells[1] if len(cells) > 1 else ""
        score_cell = cells[3] if len(cells) > 3 else ""
    elif link_cell_idx == 1:
        rank_cell = cells[2] if len(cells) > 2 else ""
        score_cell = cells[3] if len(cells) > 3 else ""
    else:
        rank_cell = cells[link_cell_idx + 1] if len(cells) > link_cell_idx + 1 else ""
        score_cell = cells[link_cell_idx + 2] if len(cells) > link_cell_idx + 2 else ""

    rank_old, rank_new, rank_delta = _parse_rank_cell(rank_cell)
    score_old, score_new, score_delta = _parse_score_cell(score_cell)

    return ChangeEntry(
        name=escape(name),
        link=link,
        movie_id=movie_id,
        rank_old=rank_old,
        rank_new=rank_new,
        rank_delta=rank_delta,
        score_old=score_old,
        score_new=score_new,
        score_delta=score_delta,
    )


def _parse_rank_cell(cell: str) -> tuple[str, str, int | None]:
    """Return (rank_old, rank_new, rank_delta) for a rank cell."""
    cell = cell.strip()
    if not cell or cell == '—':
        return '', '', None

    # New format: ↑ 189→188 (+1)
    m = _RE_NEW_RANK.search(cell)
    if m:
        old_rank, new_rank = m.group(2), m.group(3)
        try:
            delta = int(m.group(4))
        except ValueError:
            delta = None
        return old_rank, new_rank, delta

    # Old format: 58 ➡️ 59
    m = _RE_OLD_RANK.search(cell)
    if m:
        old_rank, new_rank = m.group(1), m.group(2)
        try:
            delta = int(old_rank) - int(new_rank)
        except ValueError:
            delta = None
        return old_rank, new_rank, delta

    # Plain number (new/removed tables)
    return '', cell, None


def _parse_score_cell(cell: str) -> tuple[str, str, str]:
    """Return (score_old, score_new, score_delta) for a score cell."""
    cell = cell.strip()
    if not cell or cell == '—':
        return '', '', ''

    # New format: ↑ 9.0→9.1 (+0.1)
    m = _RE_NEW_SCORE.search(cell)
    if m:
        return m.group(2), m.group(3), m.group(4)

    # Plain number like "9.2"
    return '', cell, ''


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
# HTML rendering helpers
# ---------------------------------------------------------------------------

_FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' "
            "viewBox='0 0 64 64'><rect width='64' height='64' rx='14' "
            "fill='%2300B51D'/><text x='32' y='45' font-size='34' "
            "font-weight='700' text-anchor='middle' fill='white' "
            "font-family='sans-serif'>豆</text></svg>")

_CHEVRON = ('<svg class="chev" viewBox="0 0 16 16" aria-hidden="true">'
            '<path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" '
            'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')

_ICON_FILM = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
              'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
              '<rect x="3" y="4" width="18" height="16" rx="2"/>'
              '<path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/></svg>')

_ICON_FOLDER = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>')


def _fmt_date_cn(date_str: str) -> str:
    """'2026-10-12' -> '2026年10月12日'."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{d.year}年{d.month}月{d.day}日"
    except ValueError:
        return date_str


def _weekday_cn(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return "星期" + "一二三四五六日"[d.weekday()]
    except ValueError:
        return ""


def _short_date(date_str: str, ref_year: str = "") -> str:
    """'2026-10-05' -> '10-05'; keeps the full date when the year
    differs from ref_year (some old archive files span years)."""
    parts = date_str.split('-')
    if len(parts) == 3:
        if ref_year and parts[0] != ref_year:
            return date_str
        return f"{parts[1]}-{parts[2]}"
    return date_str


def _total_of(diff: DailyDiff) -> int:
    return diff.total_changes or (
        len(diff.new_entries) + len(diff.removed_entries) + len(diff.changes))


def _movement_counts(diff: DailyDiff) -> tuple[int, int]:
    up = sum(1 for e in diff.changes if (e.rank_delta or 0) > 0)
    down = sum(1 for e in diff.changes if (e.rank_delta or 0) < 0)
    return up, down


def _delta_pill(delta: int | None) -> str:
    if delta is None or delta == 0:
        return ""
    if delta > 0:
        return f'<span class="delta delta-up">▲ {delta}</span>'
    return f'<span class="delta delta-down">▼ {abs(delta)}</span>'


def _score_delta_pill(delta_str: str) -> str:
    if not delta_str:
        return ""
    try:
        v = float(delta_str)
    except ValueError:
        return ""
    if v > 0:
        return f'<span class="delta delta-up">▲ {delta_str.lstrip("+")}</span>'
    if v < 0:
        return f'<span class="delta delta-down">▼ {delta_str.lstrip("-")}</span>'
    return ""


def _rank_cell_html(e: ChangeEntry) -> str:
    if not e.rank_new:
        return '<span class="num-muted">—</span>'
    if e.rank_old:
        return (f'<span class="rank-move"><span class="rank-from">{e.rank_old}</span>'
                f'<span class="move-arrow" aria-hidden="true">→</span>'
                f'<b class="rank-to">{e.rank_new}</b>{_delta_pill(e.rank_delta)}</span>')
    return f'<b class="rank-to">{e.rank_new}</b>'


def _score_cell_html(e: ChangeEntry) -> str:
    if not e.score_new:
        return '<span class="num-muted">—</span>'
    if e.score_old:
        return (f'<span class="score-move"><span class="score-from">{e.score_old}</span>'
                f'<span class="move-arrow" aria-hidden="true">→</span>'
                f'<b class="score-to">{e.score_new}</b>{_score_delta_pill(e.score_delta)}</span>')
    return f'<span class="score"><i class="star" aria-hidden="true">★</i><b>{e.score_new}</b></span>'


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
      <span class="brand-mark" aria-hidden="true">豆</span>
      <span class="brand-name">Top 250 变化追踪</span>
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
  <p>豆瓣 Top 250 变化追踪 · 数据每日自动更新 ·
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
  <meta name="color-scheme" content="light dark">
  <meta name="theme-color" media="(prefers-color-scheme: light)" content="#f5f4ee">
  <meta name="theme-color" media="(prefers-color-scheme: dark)" content="#15170f">
  <title>{escape(title)}</title>
  <link rel="icon" href="{_FAVICON}">
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


def _section_head(title: str, side_html: str = "") -> str:
    side = f'\n    <span class="section-side">{side_html}</span>' if side_html else ''
    return f"""<header class="section-head">
    <h2>{title}</h2>
    <span class="section-rule" aria-hidden="true"></span>{side}
  </header>"""


def _stat_strip(diff: DailyDiff) -> str:
    items = [
        (_total_of(diff), '总变更'),
        (diff.rank_changes or len(diff.changes), '排名变化'),
        (diff.score_changes, '评分变化'),
        (diff.new_count or len(diff.new_entries), '新上榜'),
        (diff.removed_count or len(diff.removed_entries), '退出榜单'),
    ]
    cells = "\n".join(
        f'<div class="stat"><b>{v}</b><span>{label}</span></div>'
        for v, label in items
    )
    return f'<div class="stat-strip">{cells}</div>'


def _entry_table(kind: str, entries: list) -> str:
    if not entries:
        return ""
    label = "新上榜" if kind == "new" else "退出榜单"
    tag_cls = "tag-new" if kind == "new" else "tag-out"

    rows = ""
    for e in entries:
        rows += f"""<tr>
      <td><a href="{e.link}" target="_blank" rel="noopener" class="movie-link">{e.name}</a></td>
      <td class="cell-rank"><b class="rank-to">{e.rank_new or '—'}</b></td>
      <td class="cell-score">{_score_cell_html(e)}</td>
    </tr>\n"""

    return f"""<div class="sub-head">
  <span class="tag {tag_cls}">{label}</span>
  <span class="sub-count">{len(entries)} 部</span>
</div>
<table class="change-table">
  <thead><tr><th>电影</th><th class="col-rank">排名</th><th class="col-score">评分</th></tr></thead>
  <tbody>{rows}  </tbody>
</table>"""


def _changes_table(changes: list) -> str:
    if not changes:
        return ""

    rows = ""
    for e in changes:
        rows += f"""<tr>
      <td><a href="{e.link}" target="_blank" rel="noopener" class="movie-link">{e.name}</a></td>
      <td class="cell-rank">{_rank_cell_html(e)}</td>
      <td class="cell-score">{_score_cell_html(e)}</td>
    </tr>\n"""

    return f"""<div class="sub-head">
  <span class="sub-dot" aria-hidden="true"></span>
  <span class="sub-label">排名及分数变化</span>
  <span class="sub-count">{len(changes)} 部</span>
</div>
<table class="change-table">
  <thead><tr><th>电影</th><th class="col-rank">排名</th><th class="col-score">评分</th></tr></thead>
  <tbody>{rows}  </tbody>
</table>"""


def _diff_card_body(diff: DailyDiff) -> str:
    parts = [
        _stat_strip(diff),
        _entry_table("new", diff.new_entries),
        _entry_table("removed", diff.removed_entries),
        _changes_table(diff.changes),
    ]
    return "\n".join(p for p in parts if p)


def _render_latest_card(diff: DailyDiff) -> str:
    weekday = _weekday_cn(diff.date)
    weekday_html = f'<span class="diff-weekday">{weekday}</span>' if weekday else ''
    return f"""<article class="diff-card is-latest">
  <header class="diff-head">
    <h3 class="diff-date">{_fmt_date_cn(diff.date)}{weekday_html}</h3>
    <span class="tag tag-latest">最新</span>
  </header>
  {_diff_card_body(diff)}
</article>"""


def _render_diff_detail(diff: DailyDiff, ref_year: str = "") -> str:
    up, down = _movement_counts(diff)
    new_n = diff.new_count or len(diff.new_entries)
    removed_n = diff.removed_count or len(diff.removed_entries)

    chips = [f'<span class="chip">{_total_of(diff)} 项变更</span>']
    if up:
        chips.append(f'<span class="chip chip-up">↑ {up}</span>')
    if down:
        chips.append(f'<span class="chip chip-down">↓ {down}</span>')
    if new_n:
        chips.append(f'<span class="chip chip-new">新 {new_n}</span>')
    if removed_n:
        chips.append(f'<span class="chip chip-out">退 {removed_n}</span>')

    weekday = _weekday_cn(diff.date)
    weekday_html = f'<span class="diff-weekday">{weekday}</span>' if weekday else ''

    return f"""<details class="diff-detail">
  <summary>
    <span class="dd-date">{_short_date(diff.date, ref_year)}</span>
    <span class="dd-chips">{''.join(chips)}</span>
    {_CHEVRON}
  </summary>
  <div class="detail-body">
    <article class="diff-card">
      <header class="diff-head">
        <h3 class="diff-date">{_fmt_date_cn(diff.date)}{weekday_html}</h3>
      </header>
      {_diff_card_body(diff)}
    </article>
  </div>
</details>"""


def _movie_cards(movies: list) -> str:
    """Render the Top 250 as a typographic ledger grid.

    Douban's CDN (img*.doubanio.com) rejects hotlinked posters with
    418/403 unless the Referer is on douban.com, so the deployed site
    can never display them — a ruled, poster-free index is used instead.
    """
    cards = ""
    for m in movies:
        rank = m.get('rank', '')
        name = escape(m.get('name', ''))
        link = m.get('link', '')
        score = m.get('score', '')

        try:
            rank_num = int(rank)
        except (ValueError, TypeError):
            rank_num = 999

        top_class = ' top-10' if rank_num <= 10 else ''
        rank_padded = str(rank_num).zfill(3) if rank_num <= 999 else escape(rank)

        cards += f"""<a class="tl-cell{top_class}" href="{link}" target="_blank" rel="noopener">
  <span class="tl-head">
    <span class="tl-rank">{rank_padded}</span>
    <span class="tl-score"><i class="star" aria-hidden="true">★</i>{escape(score)}</span>
  </span>
  <span class="tl-name">{name}</span>
</a>
"""

    return cards


def _archive_row(am: ArchiveMonth, prefix: str = "") -> str:
    if am.first_date and am.last_date:
        range_html = f'\n  <span class="ar-range">{am.first_date} ~ {am.last_date}</span>'
    else:
        range_html = ''
    return f"""<a class="archive-row" href="{prefix}{am.filename}.html">
  <span class="ar-month">{am.month_label}</span>
  <span class="ar-count"><b>{am.entry_count}</b>次更新</span>{range_html}
  <span class="ar-go" aria-hidden="true">→</span>
</a>
"""


def _empty_state(icon: str, text: str) -> str:
    return f"""<div class="empty-state">
  {icon}
  <p>{text}</p>
</div>"""


# ---------------------------------------------------------------------------
# Page renderers
# ---------------------------------------------------------------------------

def render_index(latest_diffs: list, archive_months: list, movies: list) -> str:
    """Render the home page."""
    sections = []

    # Latest diff
    if latest_diffs:
        sections.append(f"""<section class="page-section">
  {_section_head("最新变化", "每日自动更新")}
  {_render_latest_card(latest_diffs[0])}
</section>""")
    else:
        sections.append(_empty_state(_ICON_FILM, "暂无变化记录"))

    # Recent history (if more diffs in README)
    if len(latest_diffs) > 1:
        ref_year = latest_diffs[0].date[:4]
        items = "".join(_render_diff_detail(d, ref_year) for d in latest_diffs[1:])
        sections.append(f"""<section class="page-section">
  {_section_head("近期变化")}
{items}</section>""")

    # Quick archive links
    if archive_months:
        rows = "".join(_archive_row(am, prefix="archive/") for am in archive_months[:6])
        sections.append(f"""<section class="page-section">
  {_section_head("历史归档", '<a href="archive/index.html">查看全部 →</a>')}
  <div class="archive-list">
{rows}  </div>
</section>""")

    # Current Top 250 ledger
    if movies:
        sections.append(f"""<section class="page-section">
  {_section_head("当前榜单", '<a href="https://movie.douban.com/top250" target="_blank" rel="noopener">在豆瓣查看完整榜单 ↗</a>')}
  <div class="toplist">
{_movie_cards(movies)}  </div>
</section>""")

    body = "\n".join(sections)
    return _page_wrapper("豆瓣 Top250 变化追踪", "home", body)


def render_archive_index(archive_months: list) -> str:
    """Render the archive listing page."""
    if not archive_months:
        body = _empty_state(_ICON_FOLDER, "暂无归档记录")
        return _page_wrapper("历史归档", "archive", body, base_path="../")

    rows = "".join(_archive_row(am) for am in archive_months)
    body = f"""{_section_head("历史归档", f"{len(archive_months)} 个月")}
<div class="archive-list">
{rows}</div>"""

    return _page_wrapper("历史归档 - 豆瓣 Top250 变化追踪", "archive", body,
                         base_path="../")


def render_month_page(month: ArchiveMonth, prev_month: ArchiveMonth | None,
                      next_month: ArchiveMonth | None) -> str:
    """Render a monthly archive page."""
    prev_link = (f'<a class="month-arrow" href="{prev_month.filename}.html">'
                 f'← {prev_month.month_label}</a>' if prev_month else
                 '<span class="month-arrow" aria-hidden="true"></span>')
    next_link = (f'<a class="month-arrow" href="{next_month.filename}.html">'
                 f'{next_month.month_label} →</a>' if next_month else
                 '<span class="month-arrow" aria-hidden="true"></span>')

    total_updates = len(month.diffs) or month.entry_count
    total_changes = sum(_total_of(d) for d in month.diffs)
    ref_year = month.filename[:4]

    diffs_html = "".join(_render_diff_detail(d, ref_year) for d in month.diffs)

    body = f"""<div class="month-nav">
  {prev_link}
  <div class="month-center">
    <h1 class="month-title">{month.month_label}</h1>
    <p class="month-sub">{total_updates} 次更新 · {total_changes} 项变更</p>
  </div>
  {next_link}
</div>
<div class="list-toolbar">
  <span class="toolbar-label">每日记录</span>
  <button class="btn-ghost" id="toggleAll" type="button" aria-pressed="false">全部展开</button>
</div>
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
    # Files are grouped by month key (e.g. 2025-03-03.md and 2025-03-31.md
    # both belong to 2025-03) so same-month files merge into one page
    # instead of overwriting each other.
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

        existing = next((m for m in archive_months if m.filename == month_key), None)
        if existing is not None:
            # Merge into the existing month: union of day records
            known = {d.date for d in existing.diffs}
            existing.diffs.extend(d for d in diffs if d.date not in known)
            existing.diffs.sort(key=lambda d: d.date, reverse=True)
            existing.entry_count += entry_count or len(diffs)
            for date in (first_date, last_date):
                if date and date < existing.first_date:
                    existing.first_date = date
                if date and date > existing.last_date:
                    existing.last_date = date
        else:
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
    index_html = render_index(latest_diffs, archive_months, movies)
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
