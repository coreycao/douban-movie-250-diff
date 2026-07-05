import re
from datetime import date
from typing import Any, Dict, List, Tuple


PROJECT_TITLE = "Douban-Movie-250-Diff"
PROJECT_DESCRIPTION = "A diff log of the Douban top250 movies."
GITHUB_PAGES_URL = "https://coreycao.github.io/douban-movie-250-diff/"
DATE_HEADING_RE = re.compile(r'^## (\d{4}-\d{2}-\d{2})', re.MULTILINE)


def render_header(updated_date: date | str) -> str:
    """渲染 README 顶部固定信息。"""
    return (
        f"# {PROJECT_TITLE}\n\n"
        f"{PROJECT_DESCRIPTION}\n\n"
        f"[GitHub Pages]({GITHUB_PAGES_URL})\n\n"
        f"*Updated on {_date_text(updated_date)}*\n\n"
    )


def render_diff_section(section_date: date | str, changes: Any) -> str:
    """渲染单日变更章节。"""
    content = f"## {_date_text(section_date)}\n\n"
    content += render_summary(changes)
    content += "\n"

    if changes.added:
        content += "#### 新上榜电影 🆕\n\n"
        content += render_movie_table(changes.added)

    if changes.removed:
        if changes.added:
            content += "\n"
        content += "#### 退出榜单电影 ❌\n\n"
        content += render_movie_table(changes.removed)

    if changes.changed:
        content += "\n#### 排名及分数变化\n\n"
        content += render_changes_table(changes.changed)

    return content


def render_summary(changes: Any) -> str:
    """渲染变更统计摘要。"""
    rank_changes = sum(1 for old, new in changes.changed if old['rank'] != new['rank'])
    score_changes = sum(1 for old, new in changes.changed if old['score'] != new['score'])
    total_changes = len(changes.added) + len(changes.removed) + len(changes.changed)

    return (
        "### 📊 今日统计\n\n"
        f"- **总变更数**: {total_changes} 部电影\n"
        f"- **排名变化**: {rank_changes} 部\n"
        f"- **评分变化**: {score_changes} 部\n"
        f"- **新上榜**: {len(changes.added)} 部\n"
        f"- **退出榜单**: {len(changes.removed)} 部\n"
    )


def render_movie_table(movies: List[Dict[str, Any]]) -> str:
    """渲染新上榜/退出榜单电影表格。"""
    rows = [
        "|   Rank  |     Name     |   Score  |",
        "| ------- | ------------ | -------- |",
    ]
    for movie in movies:
        rows.append(f"| {movie['rank']} | [{movie['name']}]({movie['link']}) | {movie['score']} |")
    return "\n".join(rows) + "\n"


def render_changes_table(changes: List[Tuple[Dict[str, Any], Dict[str, Any]]]) -> str:
    """渲染排名/评分变化表格。"""
    rows = [
        "|     Name    |   Rank   |   Score  |",
        "| ---------- | -------- | -------- |",
    ]
    for old, new in changes:
        rows.append(
            f"| [{old['name']}]({old['link']}) | "
            f"{format_rank_change(old['rank'], new['rank'])} | "
            f"{format_score_change(old['score'], new['score'])} |"
        )
    return "\n".join(rows) + "\n"


def format_rank_change(old_rank: str, new_rank: str) -> str:
    """格式化排名变化。"""
    if old_rank == new_rank:
        return "—"

    rank_change = int(old_rank) - int(new_rank)
    if rank_change > 0:
        return f"↑ {old_rank}→{new_rank} (+{rank_change})"
    return f"↓ {old_rank}→{new_rank} ({rank_change})"


def format_score_change(old_score: str, new_score: str) -> str:
    """格式化评分变化。"""
    if old_score == new_score:
        return new_score

    score_change = float(new_score) - float(old_score)
    sign = "+" if score_change > 0 else ""
    direction = "↑" if score_change > 0 else "↓"
    return f"{direction} {old_score}→{new_score} ({sign}{score_change:.1f})"


def extract_history_sections(lines: List[str], current_date: date | str) -> List[str]:
    """提取历史章节，过滤当天章节和没有正文的空日期标题。"""
    current_heading = f"## {_date_text(current_date)}"
    sections = []
    i = 0
    while i < len(lines):
        if not DATE_HEADING_RE.match(lines[i]):
            i += 1
            continue

        start = i
        heading = lines[i].strip()
        i += 1
        while i < len(lines) and not DATE_HEADING_RE.match(lines[i]):
            i += 1

        section = lines[start:i]
        body = "".join(section[1:]).strip()
        if heading != current_heading and body:
            sections.extend(section)

    return sections


def extract_date_headings(content: str) -> List[str]:
    """提取 Markdown 中所有日期章节。"""
    return DATE_HEADING_RE.findall(content)


def _date_text(value: date | str) -> str:
    return value.isoformat() if isinstance(value, date) else value
