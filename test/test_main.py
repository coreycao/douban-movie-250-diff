import json
import os
import shutil
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

import main


class TestMainMockMode(unittest.TestCase):
    """测试 main.py 的本地 mock 运行模式"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.mock_file = os.path.join(self.test_dir, "latest_movies.json")
        self.state_file = os.path.join(self.test_dir, "recent_movies.json")
        self.readme_file = os.path.join(self.test_dir, "README.md")

        self.recent_movies = [
            {
                "rank": "1",
                "pic": "https://example.com/a.webp",
                "name": "Mock Movie A",
                "link": "https://movie.douban.com/subject/1000001",
                "score": "9.7",
                "id": "1000001"
            },
            {
                "rank": "2",
                "pic": "https://example.com/b.webp",
                "name": "Mock Movie B",
                "link": "https://movie.douban.com/subject/1000002",
                "score": "9.6",
                "id": "1000002"
            }
        ]
        self.latest_movies = [
            {
                "rank": "1",
                "pic": "https://example.com/a.webp",
                "name": "Mock Movie A",
                "link": "https://movie.douban.com/subject/1000001",
                "score": "9.8",
                "id": "1000001"
            },
            {
                "rank": "2",
                "pic": "https://example.com/c.webp",
                "name": "Mock Movie C",
                "link": "https://movie.douban.com/subject/1000003",
                "score": "9.5",
                "id": "1000003"
            }
        ]

        with open(self.mock_file, 'w', encoding='utf-8') as f:
            json.dump(self.latest_movies, f)
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.recent_movies, f)
        with open(self.readme_file, 'w', encoding='utf-8') as f:
            f.write("# Douban-Movie-250-Diff\n\n")
            f.write("A diff log of the Douban top250 movies.\n\n")
            f.write("*Updated on 2026-06-01*\n\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_run_with_mock_data_does_not_fetch_douban(self):
        """mock 模式应使用本地数据，不实例化真实爬虫"""
        with patch('main.MovieSpider') as mock_spider:
            main.run([
                '--mock', self.mock_file,
                '--state-file', self.state_file,
                '--readme-file', self.readme_file
            ])

        mock_spider.assert_not_called()

        with open(self.readme_file, 'r', encoding='utf-8') as f:
            readme_content = f.read()
        self.assertIn(f"## {date.today().isoformat()}", readme_content)
        self.assertIn("新上榜电影", readme_content)
        self.assertIn("退出榜单电影", readme_content)
        self.assertIn("排名及分数变化", readme_content)
        self.assertIn("Mock Movie C", readme_content)

        with open(self.state_file, 'r', encoding='utf-8') as f:
            saved_movies = json.load(f)
        self.assertEqual(saved_movies, self.latest_movies)

    def test_load_mock_movies_requires_movie_array(self):
        """mock 文件必须是电影对象数组"""
        invalid_mock_file = os.path.join(self.test_dir, "invalid.json")
        with open(invalid_mock_file, 'w', encoding='utf-8') as f:
            json.dump({"movies": []}, f)

        with self.assertRaises(ValueError):
            main.load_mock_movies(invalid_mock_file)

    def test_load_mock_movies_validates_required_fields(self):
        """mock 电影对象必须包含主流程所需字段"""
        invalid_mock_file = os.path.join(self.test_dir, "missing_fields.json")
        with open(invalid_mock_file, 'w', encoding='utf-8') as f:
            json.dump([{"id": "1000001", "name": "Incomplete"}], f)

        with self.assertRaises(ValueError) as context:
            main.load_mock_movies(invalid_mock_file)

        self.assertIn("missing required fields", str(context.exception))


if __name__ == '__main__':
    unittest.main()
