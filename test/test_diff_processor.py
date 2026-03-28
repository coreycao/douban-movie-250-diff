import unittest
import json
import os
import tempfile
import shutil
from unittest.mock import patch, mock_open
from datetime import date
from src.diff_processor import DiffProcessor, MovieChanges


class TestMovieChanges(unittest.TestCase):
    """测试 MovieChanges 类"""

    def test_has_changes_with_added(self):
        """有新增时返回 True"""
        changes = MovieChanges(
            added=[{'id': '1'}],
            removed=[],
            changed=[]
        )
        self.assertTrue(changes.has_changes())

    def test_has_changes_with_removed(self):
        """有移除时返回 True"""
        changes = MovieChanges(
            added=[],
            removed=[{'id': '1'}],
            changed=[]
        )
        self.assertTrue(changes.has_changes())

    def test_has_changes_with_changed(self):
        """有变化时返回 True"""
        changes = MovieChanges(
            added=[],
            removed=[],
            changed=[({'id': '1'}, {'id': '1'})]
        )
        self.assertTrue(changes.has_changes())

    def test_has_changes_no_changes(self):
        """无变化时返回 False"""
        changes = MovieChanges(
            added=[],
            removed=[],
            changed=[]
        )
        self.assertFalse(changes.has_changes())


class TestDiffProcessorCompareMovies(unittest.TestCase):
    """测试电影对比逻辑"""

    def setUp(self):
        self.processor = DiffProcessor()

    def test_added_movies(self):
        """检测新增电影"""
        recent = [
            {'id': '1', 'rank': '1', 'name': 'Movie A', 'score': '9.0'},
        ]
        latest = [
            {'id': '1', 'rank': '1', 'name': 'Movie A', 'score': '9.0'},
            {'id': '2', 'rank': '2', 'name': 'Movie B', 'score': '8.5'},
        ]

        changes = self.processor._compare_movies(recent, latest)

        self.assertEqual(len(changes.added), 1)
        self.assertEqual(changes.added[0]['id'], '2')
        self.assertEqual(len(changes.removed), 0)
        self.assertEqual(len(changes.changed), 0)

    def test_removed_movies(self):
        """检测移除电影"""
        recent = [
            {'id': '1', 'rank': '1', 'name': 'Movie A', 'score': '9.0'},
            {'id': '2', 'rank': '2', 'name': 'Movie B', 'score': '8.5'},
        ]
        latest = [
            {'id': '1', 'rank': '1', 'name': 'Movie A', 'score': '9.0'},
        ]

        changes = self.processor._compare_movies(recent, latest)

        self.assertEqual(len(changes.removed), 1)
        self.assertEqual(changes.removed[0]['id'], '2')
        self.assertEqual(len(changes.added), 0)
        self.assertEqual(len(changes.changed), 0)

    def test_rank_changes(self):
        """检测排名变化"""
        recent = [
            {'id': '1', 'rank': '1', 'name': 'Movie A', 'score': '9.0'},
        ]
        latest = [
            {'id': '1', 'rank': '2', 'name': 'Movie A', 'score': '9.0'},
        ]

        changes = self.processor._compare_movies(recent, latest)

        self.assertEqual(len(changes.changed), 1)
        self.assertEqual(changes.changed[0][0]['rank'], '1')
        self.assertEqual(changes.changed[0][1]['rank'], '2')

    def test_score_changes(self):
        """检测评分变化"""
        recent = [
            {'id': '1', 'rank': '1', 'name': 'Movie A', 'score': '9.0'},
        ]
        latest = [
            {'id': '1', 'rank': '1', 'name': 'Movie A', 'score': '9.1'},
        ]

        changes = self.processor._compare_movies(recent, latest)

        self.assertEqual(len(changes.changed), 1)
        self.assertEqual(changes.changed[0][0]['score'], '9.0')
        self.assertEqual(changes.changed[0][1]['score'], '9.1')

    def test_both_rank_and_score_changes(self):
        """检测排名和评分同时变化"""
        recent = [
            {'id': '1', 'rank': '1', 'name': 'Movie A', 'score': '9.0'},
        ]
        latest = [
            {'id': '1', 'rank': '2', 'name': 'Movie A', 'score': '9.1'},
        ]

        changes = self.processor._compare_movies(recent, latest)

        self.assertEqual(len(changes.changed), 1)

    def test_no_changes(self):
        """无变化检测"""
        recent = [
            {'id': '1', 'rank': '1', 'name': 'Movie A', 'score': '9.0'},
        ]
        latest = [
            {'id': '1', 'rank': '1', 'name': 'Movie A', 'score': '9.0'},
        ]

        changes = self.processor._compare_movies(recent, latest)

        self.assertEqual(len(changes.added), 0)
        self.assertEqual(len(changes.removed), 0)
        self.assertEqual(len(changes.changed), 0)
        self.assertFalse(changes.has_changes())

    def test_mixed_changes(self):
        """测试混合变化场景"""
        recent = [
            {'id': '1', 'rank': '1', 'name': 'A', 'score': '9.0'},
            {'id': '2', 'rank': '2', 'name': 'B', 'score': '8.5'},
            {'id': '3', 'rank': '3', 'name': 'C', 'score': '8.0'},
        ]
        latest = [
            {'id': '1', 'rank': '2', 'name': 'A', 'score': '9.0'},  # 排名变化
            {'id': '4', 'rank': '1', 'name': 'D', 'score': '9.5'},  # 新增
            {'id': '3', 'rank': '3', 'name': 'C', 'score': '8.1'},  # 评分变化
            # 'id': '2' 被移除
        ]

        changes = self.processor._compare_movies(recent, latest)

        self.assertEqual(len(changes.added), 1)
        self.assertEqual(changes.added[0]['id'], '4')
        self.assertEqual(len(changes.removed), 1)
        self.assertEqual(changes.removed[0]['id'], '2')
        self.assertEqual(len(changes.changed), 2)

    def test_compare_by_id_not_name(self):
        """验证按 ID 而非名称比较"""
        recent = [
            {'id': '1', 'rank': '1', 'name': 'Old Name', 'score': '9.0'},
        ]
        latest = [
            {'id': '1', 'rank': '1', 'name': 'New Name', 'score': '9.0'},
        ]

        changes = self.processor._compare_movies(recent, latest)

        # 名称变化不应被视为变化
        self.assertEqual(len(changes.changed), 0)

    def test_empty_lists(self):
        """测试空列表"""
        changes = self.processor._compare_movies([], [])
        self.assertFalse(changes.has_changes())

    def test_all_new_movies(self):
        """测试全部是新电影"""
        changes = self.processor._compare_movies([], [
            {'id': '1', 'rank': '1', 'name': 'A', 'score': '9.0'},
        ])
        self.assertEqual(len(changes.added), 1)

    def test_all_removed_movies(self):
        """测试全部电影被移除"""
        changes = self.processor._compare_movies([
            {'id': '1', 'rank': '1', 'name': 'A', 'score': '9.0'},
        ], [])
        self.assertEqual(len(changes.removed), 1)


class TestDiffProcessorFormatting(unittest.TestCase):
    """测试格式化输出"""

    def setUp(self):
        self.processor = DiffProcessor()

    def test_format_movie_table(self):
        """测试电影表格格式"""
        movies = [
            {
                'rank': '1',
                'name': '肖申克的救赎',
                'score': '9.7',
                'link': 'https://movie.douban.com/subject/1/'
            },
            {
                'rank': '2',
                'name': '霸王别姬',
                'score': '9.6',
                'link': 'https://movie.douban.com/subject/2/'
            },
        ]

        table = self.processor._format_movie_table(movies)

        self.assertIn('|   Rank  |', table)
        self.assertIn('| ------- |', table)
        self.assertIn('| 1 |', table)
        self.assertIn('[肖申克的救赎](https://movie.douban.com/subject/1/)', table)
        self.assertIn('| 9.7 |', table)

    def test_format_changes_table(self):
        """测试变更表格格式"""
        changes = [
            (
                {'rank': '1', 'score': '9.0', 'name': 'Movie A', 'link': 'https://example.com/1/'},
                {'rank': '2', 'score': '9.1', 'name': 'Movie A', 'link': 'https://example.com/1/'}
            )
        ]

        table = self.processor._format_changes_table(changes)

        self.assertIn('|     Name    |', table)
        # 排名下降，显示 ↓ 和变化幅度
        self.assertIn('↓ 1→2', table)
        self.assertIn('(-1)', table)
        # 评分上升，显示 ↑ 和变化幅度
        self.assertIn('↑ 9.0→9.1', table)
        self.assertIn('(+0.1)', table)

    def test_format_changes_table_no_rank_change(self):
        """测试排名不变时的格式"""
        changes = [
            (
                {'rank': '1', 'score': '9.0', 'name': 'A', 'link': 'https://example.com/'},
                {'rank': '1', 'score': '9.1', 'name': 'A', 'link': 'https://example.com/'}
            )
        ]

        table = self.processor._format_changes_table(changes)

        # 排名不变应显示 —
        self.assertIn('| — |', table)
        # 评分变化
        self.assertIn('↑ 9.0→9.1', table)
        self.assertIn('(+0.1)', table)

    def test_generate_summary(self):
        """测试统计摘要生成"""
        changes = MovieChanges(
            added=[{'id': '1'}],
            removed=[{'id': '2'}],
            changed=[
                ({'rank': '1', 'score': '9.0', 'id': '3'}, {'rank': '2', 'score': '9.0', 'id': '3'}),
                ({'rank': '3', 'score': '8.0', 'id': '4'}, {'rank': '3', 'score': '8.1', 'id': '4'}),
            ]
        )

        summary = self.processor._generate_summary(changes)

        self.assertIn('📊', summary)
        self.assertIn('总变更数**: 4', summary)
        self.assertIn('排名变化**: 1', summary)
        self.assertIn('评分变化**: 1', summary)
        self.assertIn('新上榜**: 1', summary)
        self.assertIn('退出榜单**: 1', summary)

    def test_generate_summary_no_changes(self):
        """测试无变化时的统计摘要"""
        changes = MovieChanges(added=[], removed=[], changed=[])

        summary = self.processor._generate_summary(changes)

        self.assertIn('总变更数**: 0', summary)
        self.assertIn('排名变化**: 0', summary)
        self.assertIn('评分变化**: 0', summary)
        self.assertIn('新上榜**: 0', summary)
        self.assertIn('退出榜单**: 0', summary)


class TestDiffProcessorIntegration(unittest.TestCase):
    """测试 DiffProcessor 集成功能"""

    def setUp(self):
        """每个测试前创建临时目录"""
        self.test_dir = tempfile.mkdtemp()
        self.original_paths = {
            'movie_list_filename': os.path.join(self.test_dir, 'movies.json'),
            'readme_filename': os.path.join(self.test_dir, 'README.md'),
            'archive_dir': os.path.join(self.test_dir, 'archive')
        }

        # patch PATHS
        self.paths_patcher = patch('src.diff_processor.PATHS', self.original_paths)
        self.paths_patcher.start()

        self.processor = DiffProcessor()

    def tearDown(self):
        """每个测试后清理临时目录"""
        self.paths_patcher.stop()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_first_run_creates_files(self):
        """首次运行应创建初始文件"""
        latest_movies = [
            {'id': '1', 'rank': '1', 'name': 'A', 'score': '9.0', 'link': 'x', 'pic': 'x'}
        ]

        result = self.processor.process_diff(latest_movies)

        self.assertTrue(result)
        # 验证 JSON 文件创建
        self.assertTrue(os.path.exists(self.original_paths['movie_list_filename']))
        # 验证 README 文件创建
        self.assertTrue(os.path.exists(self.original_paths['readme_filename']))

        # 验证 JSON 内容
        with open(self.original_paths['movie_list_filename'], 'r', encoding='utf-8') as f:
            saved_movies = json.load(f)
        self.assertEqual(saved_movies, latest_movies)

        # 验证 README 内容
        with open(self.original_paths['readme_filename'], 'r', encoding='utf-8') as f:
            readme_content = f.read()
        self.assertIn('Douban-Movie-250-Diff', readme_content)
        self.assertIn(str(date.today()), readme_content)

    def test_no_changes_no_update(self):
        """无变化时不更新 README"""
        # 首次运行
        movies = [
            {'id': '1', 'rank': '1', 'name': 'A', 'score': '9.0', 'link': 'x', 'pic': 'x'}
        ]
        self.processor.process_diff(movies)

        # 获取 README 修改时间
        readme_mtime = os.path.getmtime(self.original_paths['readme_filename'])

        # 再次运行相同数据
        result = self.processor.process_diff(movies)

        self.assertFalse(result)
        # README 修改时间应不变
        self.assertEqual(
            os.path.getmtime(self.original_paths['readme_filename']),
            readme_mtime
        )

    def test_with_changes_updates_readme(self):
        """有变化时更新 README"""
        # 首次运行
        initial_movies = [
            {'id': '1', 'rank': '1', 'name': 'A', 'score': '9.0', 'link': 'x', 'pic': 'x'}
        ]
        self.processor.process_diff(initial_movies)

        # 运行有变化的数据
        updated_movies = [
            {'id': '1', 'rank': '2', 'name': 'A', 'score': '9.0', 'link': 'x', 'pic': 'x'},
            {'id': '2', 'rank': '1', 'name': 'B', 'score': '8.5', 'link': 'y', 'pic': 'y'}
        ]
        result = self.processor.process_diff(updated_movies)

        self.assertTrue(result)

        # 验证 README 内容更新
        with open(self.original_paths['readme_filename'], 'r', encoding='utf-8') as f:
            readme_content = f.read()

        self.assertIn('## ' + str(date.today()), readme_content)
        self.assertIn('新上榜电影', readme_content)
        self.assertIn('[B](y)', readme_content)
        self.assertIn('排名及分数变化', readme_content)

    def test_load_recent_movies_file_not_found(self):
        """测试 JSON 文件不存在时返回空列表"""
        movies = self.processor._load_recent_movies()
        self.assertEqual(movies, [])

    def test_load_recent_movies_invalid_json(self):
        """测试 JSON 文件损坏时返回空列表"""
        # 创建无效 JSON 文件
        with open(self.original_paths['movie_list_filename'], 'w') as f:
            f.write('invalid json content')

        movies = self.processor._load_recent_movies()
        self.assertEqual(movies, [])

    def test_save_and_load_movies(self):
        """测试保存和加载电影数据"""
        movies = [
            {'id': '1', 'rank': '1', 'name': '测试', 'score': '9.0', 'link': 'x', 'pic': 'x'}
        ]

        self.processor._save_latest_movies(movies)
        loaded_movies = self.processor._load_recent_movies()

        self.assertEqual(loaded_movies, movies)


if __name__ == '__main__':
    unittest.main()
