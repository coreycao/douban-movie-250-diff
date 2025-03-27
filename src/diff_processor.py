import json
from datetime import date
from typing import Dict, List, Set, Tuple, Any
from src.common import PATHS, log, write_text
from src.spider import MovieSpider


class DiffProcessor:
    def __init__(self):
        self.movie_list_file = PATHS['movie_list_filename']
        self.readme_file = PATHS['readme_filename']

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
        content = "# Douban-Movie-250-Diff\n\n" \
                  "A diff log of the Douban top250 movies.\n" \
                  f"*Updated on {date.today().isoformat()}*\n"
        write_text(self.readme_file, 'w', content)

    def _update_readme(self, changes: 'MovieChanges') -> None:
        """更新README文件，添加变更记录"""
        today = date.today().isoformat()
        content = f"## {today}\n\n"

        if changes.added or changes.removed:
            if changes.added:
                content += "#### 新上榜电影\n\n"
                content += self._format_movie_table(changes.added)
            if changes.removed:
                content += "\n#### 退出榜单电影\n\n"
                content += self._format_movie_table(changes.removed)

        if changes.changed:
            content += "\n#### 排名及分数变化\n\n"
            content += self._format_changes_table(changes.changed)

        try:
            with open(self.readme_file, 'r+', encoding='utf-8') as f:
                old_content = f.readlines()
                f.seek(0)
                f.write("# Douban-Movie-250-Diff\n\n" \
                        "A diff log of the Douban top250 movies.\n\n" \
                        f"*Updated on {today}*\n\n")
                f.write(content)
                if len(old_content) > 6:
                    f.writelines(old_content[6:])
                f.truncate()
        except Exception as e:
            log(f"Failed to update README: {str(e)}")

    def _format_movie_table(self, movies: List[Dict[str, Any]]) -> str:
        """格式化电影表格"""
        table = "|   Rank  |     Name     |   Score  |\n"
        table += "| ------- | ------------ | -------- |\n"
        for movie in movies:
            table += "| {rank} | [{name}]({link}) | {score} |\n".format(
                rank=movie['rank'],
                name=movie['name'],
                link=movie['link'],
                score=movie['score']
            )
        return table

    def _format_changes_table(self, changes: List[Tuple[Dict[str, Any], Dict[str, Any]]]) -> str:
        """格式化变更表格"""
        table = "|     Name    |   Rank   |   Score  |\n"
        table += "| ---------- | -------- | -------- |\n"
        for old, new in changes:
            rank_diff = old['rank'] if old['rank'] == new['rank'] else f"{old['rank']}➡️{new['rank']}"
            score_diff = old['score'] if old['score'] == new['score'] else f"{old['score']}➡️{new['score']}"
            table += "| [{name}]({link}) | {rank} | {score} |\n".format(
                name=old['name'],
                link=old['link'],
                rank=rank_diff,
                score=score_diff
            )
        return table


class MovieChanges:
    """电影变更记录类"""
    def __init__(self, added: List[Dict[str, Any]], removed: List[Dict[str, Any]],
                 changed: List[Tuple[Dict[str, Any], Dict[str, Any]]]):
        self.added = added
        self.removed = removed
        self.changed = changed

    def has_changes(self) -> bool:
        """检查是否有变更"""
        return bool(self.added or self.removed or self.changed)