import json
import os
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Tuple, Any
from src.common import PATHS, log, write_text_atomic
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
        """处理电影列表差异并生成报告。

        失败时抛出异常（由调用方决定退出码），绝不吞错；
        README 先写成功、state 后写，写 README 失败时 state 保持不变，
        下次运行会重试同一批变更，保证变更不会被静默丢弃。
        """
        recent_movies = self._load_recent_movies()
        if not recent_movies:  # 首次运行
            self._create_initial_readme()
            self._save_latest_movies(latest_movies)
            return True

        changes = self._compare_movies(recent_movies, latest_movies)
        if changes.has_changes():
            self._update_readme(changes)
            self._save_latest_movies(latest_movies)
            return True
        return False

    def _load_recent_movies(self) -> List[Dict[str, Any]]:
        """加载最近的电影列表。

        文件不存在视为首次运行；文件存在但损坏则大声失败——
        绝不能静默当作首次运行，否则 README 历史会被整体重置。
        """
        if not os.path.exists(self.movie_list_file):
            log(f"State file {self.movie_list_file} not found; starting fresh")
            return []
        try:
            with open(self.movie_list_file, 'r', encoding='utf-8') as f:
                movies = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            raise RuntimeError(
                f"State file {self.movie_list_file} exists but cannot be parsed; "
                f"refusing to reset diff history. Restore or fix the file first. ({e})"
            )
        if not isinstance(movies, list):
            raise RuntimeError(
                f"State file {self.movie_list_file} must contain a JSON array, "
                f"got {type(movies).__name__}"
            )
        return movies

    def _save_latest_movies(self, movies: List[Dict[str, Any]]) -> None:
        """原子保存最新的电影列表"""
        write_text_atomic(self.movie_list_file, json.dumps(movies, ensure_ascii=False, indent=2))

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
        """创建初始README文件。

        若 README 中已有历史章节则原样保留——state 丢失时绝不能静默清空 diff 历史。
        """
        today = date.today()
        history_sections = []
        if os.path.exists(self.readme_file):
            try:
                with open(self.readme_file, 'r', encoding='utf-8') as f:
                    history_sections = extract_history_sections(f.readlines(), today)
            except IOError as e:
                log(f"Could not read existing README: {e}")
            if history_sections:
                log("Existing README history found; preserving it")
        content = render_header(today)
        if history_sections and not content.endswith("\n\n"):
            content += "\n"
        content += "".join(history_sections)
        write_text_atomic(self.readme_file, content)

    def _update_readme(self, changes: 'MovieChanges') -> None:
        """更新README文件，添加变更记录。

        失败时抛出异常——调用方依赖这一点在推进 state 前中止。
        """
        today = date.today()
        with open(self.readme_file, 'r', encoding='utf-8') as f:
            old_content = f.readlines()

        content = render_header(today)
        content += render_diff_section(today, changes)
        history_sections = extract_history_sections(old_content, today)
        if history_sections and not content.endswith("\n\n"):
            content += "\n"
        content += "".join(history_sections)
        write_text_atomic(self.readme_file, content)

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
