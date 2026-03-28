import datetime
import os
import re
from src.common import PATHS, log


def parse_archive_dates(filepath: str) -> tuple:
    """
    从归档文件中提取所有日期，返回第一个和最后一个日期

    Args:
        filepath: 归档文件路径

    Returns:
        (first_date, last_date) 或 (None, None) 如果没有找到日期
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 查找所有 ## YYYY-MM-DD 格式的日期
        dates = re.findall(r'^## (\d{4}-\d{2}-\d{2})', content, re.MULTILINE)

        if dates:
            return dates[0], dates[-1]
        return None, None
    except Exception as e:
        log(f"Error parsing dates from {filepath}: {e}")
        return None, None


def count_entries_and_movies(filepath: str) -> tuple:
    """
    统计归档文件中的条目数和有变化的电影数

    Args:
        filepath: 归档文件路径

    Returns:
        (entries_count, unique_movies_count)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 统计日期条目数
        entries = len(re.findall(r'^## \d{4}-\d{2}-\d{2}', content, re.MULTILINE))

        # 统计唯一电影数（通过链接数量）
        movies = re.findall(r'\[([^\]]+)\]\(https://movie\.douban\.com/subject/\d+/', content)
        unique_movies = len(set(movies))

        return entries, unique_movies
    except Exception as e:
        log(f"Error counting entries from {filepath}: {e}")
        return 0, 0


def generate_index_entry(filename: str, is_new_format: bool = False) -> dict:
    """
    为单个归档文件生成索引条目信息

    Args:
        filename: 归档文件名（如 2025-08.md 或 2025-08-30.md）
        is_new_format: 是否为新格式文件

    Returns:
        包含索引信息的字典
    """
    filepath = os.path.join(PATHS['archive_dir'], filename)
    first_date, last_date = parse_archive_dates(filepath)
    entries, movies = count_entries_and_movies(filepath)

    entry = {
        'filename': filename,
        'first_date': first_date,
        'last_date': last_date,
        'entries': entries,
        'movies': movies
    }

    # 从文件名提取月份或日期
    if is_new_format:
        # 新格式: YYYY-MM.md
        month_match = re.match(r'(\d{4}-\d{2})\.md', filename)
        entry['month'] = month_match.group(1) if month_match else None
    else:
        # 旧格式: YYYY-MM-DD.md
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})\.md', filename)
        entry['archived_date'] = date_match.group(1) if date_match else None

    return entry


def update_index():
    """更新归档索引文件"""
    archive_dir = PATHS['archive_dir']
    index_path = os.path.join(archive_dir, 'INDEX.md')

    # 获取所有归档文件
    try:
        files = sorted([f for f in os.listdir(archive_dir) if f.endswith('.md') and f != 'INDEX.md'], reverse=True)
    except FileNotFoundError:
        os.makedirs(archive_dir, exist_ok=True)
        files = []

    # 分类文件
    new_format_files = []
    old_format_files = []

    for filename in files:
        if re.match(r'\d{4}-\d{2}\.md', filename):
            new_format_files.append(filename)
        else:
            old_format_files.append(filename)

    # 生成索引内容
    content = "# Archive Index\n\n"
    content += "Historical changes archived by month.\n\n"

    # 新格式索引
    if new_format_files:
        content += "## Monthly Archives\n\n"
        content += "| Month | Date Range | File | Entries | Movies Changed |\n"
        content += "|-------|------------|------|---------|----------------|\n"

        for filename in sorted(new_format_files, reverse=True):
            entry = generate_index_entry(filename, is_new_format=True)
            date_range = f"{entry['first_date']} ~ {entry['last_date']}" if entry['first_date'] and entry['last_date'] else "N/A"
            content += f"| {entry['month']} | {date_range} | {entry['filename']} | {entry['entries']} | {entry['movies']} |\n"

    # 旧格式索引
    if old_format_files:
        content += "\n## Legacy Archives (Old Format)\n\n"
        content += "| Archived Date | Date Range | File | Entries |\n"
        content += "|---------------|------------|------|---------|\n"

        for filename in sorted(old_format_files, reverse=True):
            entry = generate_index_entry(filename, is_new_format=False)
            date_range = f"{entry['first_date']} ~ {entry['last_date']}" if entry['first_date'] and entry['last_date'] else "N/A"
            content += f"| {entry['archived_date']} | {date_range} | {entry['filename']} | {entry['entries']} |\n"

    # 写入索引文件
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(content)

    log("Index updated successfully")


def archive_data():
    """归档数据 - 使用新格式"""
    today = datetime.date.today()

    # 读取当前 README
    try:
        with open(PATHS['readme_filename'], 'r', encoding='utf-8') as f_readme:
            lines = f_readme.readlines()
    except FileNotFoundError:
        log("README file not found")
        return

    # 查找第一个日期条目
    first_date = None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            first_date = line.strip().split(" ")[1]
            break

    if not first_date:
        log("No date entries found in README")
        return

    # 解析日期获取月份
    try:
        date_obj = datetime.datetime.strptime(first_date, '%Y-%m-%d')
        month_str = date_obj.strftime('%Y-%m')
    except ValueError:
        log(f"Invalid date format: {first_date}")
        return

    # 提取内容（跳过 README 头部）
    content_start = None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            content_start = i
            break

    if content_start is None:
        log("No content to archive")
        return

    archive_lines = lines[content_start:]

    # 统计条目数
    entries = len([line for line in archive_lines if line.startswith("## ")])

    # 解析最后一个日期
    last_date = first_date
    for line in reversed(archive_lines):
        if line.startswith("## "):
            last_date = line.strip().split(" ")[1]
            break

    # 生成归档文件内容（新格式）
    archive_content = f"<!-- Archive: {month_str} -->\n"
    archive_content += f"<!-- Date Range: {first_date} ~ {last_date} -->\n"
    archive_content += f"<!-- Archived: {today.isoformat()} -->\n"
    archive_content += f"<!-- Total Entries: {entries} -->\n"
    archive_content += "\n"
    archive_content += "".join(archive_lines)

    # 写入归档文件
    os.makedirs(PATHS['archive_dir'], exist_ok=True)
    archive_filename = os.path.join(PATHS['archive_dir'], f"{month_str}.md")

    with open(archive_filename, 'w', encoding='utf-8') as f_archive:
        f_archive.writelines(archive_content)

    log(f"Archived to {month_str}.md")

    # 更新索引
    update_index()

    # 重置 README
    md_head = "# Douban-Movie-250-Diff\n\n" \
              "A diff log of the Douban top250 movies.\n\n" \
              f"*Updated on {today.isoformat()}*\n\n"
    md_content = f"## {today.isoformat()}\n\n"
    newlines = [md_head, md_content]

    with open(PATHS['readme_filename'], 'w', encoding='utf-8') as f:
        f.writelines(newlines)

    log("README reset complete")


if __name__ == "__main__":
    log("archive data start")
    archive_data()
