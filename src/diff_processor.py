import json
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Tuple, Any
from src.common import PATHS, log, write_text
from src.readme_renderer import (
    extract_history_sections,
    render_changes_table,
    render_diff_section,
    render_header,
    render_movie_table,
    render_summary,
)


class DiffProcessor:
    def __init__(self, movie_list_file: str = None, readme_file: str = None):
        self.movie_list_file = movie_list_file or PATHS['movie_list_filename']
        self.readme_file = readme_file or PATHS['readme_filename']

    def process_diff(self, latest_movies: List[Dict[str, Any]]) -> bool:
        """处理电影列表差异并生成报告"""
        try:
            recent_movies = self._load_recent_movies()
            if not recent_movies:  # 首次运行或加载失败
                self._save_latest_movies(latest_movies)
                self._create_initial_readme()
                return True

            changes = self._compare_movies(recent_movies, latest_movies)
            if changes.has_changes():
                self._update_readme(changes)
                self._save_latest_movies(latest_movies)
                return True
            return False

        except Exception as e:
            log(f"Error processing diff: {str(e)}")
            return False

    def _load_recent_movies(self) -> List[Dict[str, Any]]:
        """加载最近的电影列表"""
        try:
            with open(self.movie_list_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            log(f"Failed to load recent movies: {str(e)}")
            return []

    def _save_latest_movies(self, movies: List[Dict[str, Any]]) -> None:
        """保存最新的电影列表"""
        with open(self.movie_list_file, 'w', encoding='utf-8') as f:
            json.dump(movies, f, ensure_ascii=False, indent=2)

    def _compare_movies(self, recent: List[Dict[str, Any]], latest: List[Dict[str, Any]]) -> 'MovieChanges':
        """比较新旧电影列表的差异"""
        recent_dict = {movie['id']: movie for movie in recent}
        latest_dict = {movie['id']: movie for movie in latest}
        
        recent_ids = set(recent_dict.keys())
        latest_ids = set(latest_dict.keys())
        
        removed = recent_ids - latest_ids
        added = latest_ids - recent_ids
        
        changed = []
        for movie_id in recent_ids & latest_ids:
            old = recent_dict[movie_id]
            new = latest_dict[movie_id]
            if old['rank'] != new['rank'] or old['score'] != new['score']:
                changed.append((old, new))
        
        return MovieChanges(
            added=[latest_dict[id] for id in added],
            removed=[recent_dict[id] for id in removed],
            changed=changed
        )

    def _create_initial_readme(self) -> None:
        """创建初始README文件"""
        content = render_header(date.today())
        write_text(self.readme_file, 'w', content)

    def _update_readme(self, changes: 'MovieChanges') -> None:
        """更新README文件，添加变更记录"""
        today = date.today()
        content = render_diff_section(today, changes)

        try:
            with open(self.readme_file, 'r+', encoding='utf-8') as f:
                old_content = f.readlines()
                f.seek(0)
                f.write(render_header(today))
                f.write(content)
                history_sections = self._extract_history_sections(old_content, today)
                if history_sections and not content.endswith("\n\n"):
                    f.write("\n")
                f.writelines(history_sections)
                f.truncate()
        except Exception as e:
            log(f"Failed to update README: {str(e)}")

    def _extract_history_sections(self, lines: List[str], current_date: date | str) -> List[str]:
        """提取历史章节，过滤当天章节和没有正文的空日期标题。"""
        return extract_history_sections(lines, current_date)

    def _format_movie_table(self, movies: List[Dict[str, Any]]) -> str:
        """格式化电影表格"""
        return render_movie_table(movies)

    def _generate_summary(self, changes: 'MovieChanges') -> str:
        """生成变更统计摘要"""
        return render_summary(changes)

    def _format_changes_table(self, changes: List[Tuple[Dict[str, Any], Dict[str, Any]]]) -> str:
        """格式化变更表格，增强显示变化方向和幅度"""
        return render_changes_table(changes)


@dataclass
class MovieChanges:
    """电影变更记录类"""
    added: List[Dict[str, Any]]
    removed: List[Dict[str, Any]]
    changed: List[Tuple[Dict[str, Any], Dict[str, Any]]]

    def has_changes(self) -> bool:
        """检查是否有变更"""
        return bool(self.added or self.removed or self.changed)
