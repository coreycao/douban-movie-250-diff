import unittest
import os
import tempfile
import shutil
from unittest.mock import patch
from archive import parse_archive_dates, count_entries_and_movies, generate_index_entry


class TestParseArchiveDates(unittest.TestCase):
    """测试日期解析函数"""

    def test_parse_new_format(self):
        """测试解析新格式归档文件"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("<!-- Archive: 2025-08 -->\n")
            f.write("<!-- Date Range: 2025-08-01 ~ 2025-08-30 -->\n")
            f.write("\n")
            f.write("## 2025-08-30\n\n")
            f.write("Content here\n")
            f.write("\n")
            f.write("## 2025-08-15\n\n")
            f.write("More content\n")
            f.write("\n")
            f.write("## 2025-08-01\n\n")
            f.write("First entry\n")
            temp_path = f.name

        try:
            first, last = parse_archive_dates(temp_path)
            self.assertEqual(first, "2025-08-30")
            self.assertEqual(last, "2025-08-01")
        finally:
            os.unlink(temp_path)

    def test_parse_old_format(self):
        """测试解析旧格式归档文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Douban-Movie-250-Diff\n\n")
            f.write("A diff log of the Douban top250 movies.\n\n")
            f.write("*Updated on 2025-03-03*\n\n")
            f.write("## 2025-03-03\n\n")
            f.write("Content\n")
            f.write("\n")
            f.write("## 2025-02-24\n\n")
            f.write("More content\n")
            temp_path = f.name

        try:
            first, last = parse_archive_dates(temp_path)
            self.assertEqual(first, "2025-03-03")
            self.assertEqual(last, "2025-02-24")
        finally:
            os.unlink(temp_path)

    def test_parse_empty_file(self):
        """测试解析空文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            temp_path = f.name

        try:
            first, last = parse_archive_dates(temp_path)
            self.assertIsNone(first)
            self.assertIsNone(last)
        finally:
            os.unlink(temp_path)

    def test_parse_no_dates(self):
        """测试解析没有日期的文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Some content\n")
            f.write("But no dates\n")
            temp_path = f.name

        try:
            first, last = parse_archive_dates(temp_path)
            self.assertIsNone(first)
            self.assertIsNone(last)
        finally:
            os.unlink(temp_path)


class TestCountEntriesAndMovies(unittest.TestCase):
    """测试条目和电影计数函数"""

    def test_count_new_format(self):
        """测试统计新格式文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("<!-- Archive: 2025-08 -->\n")
            f.write("## 2025-08-30\n\n")
            f.write("| [Movie A](https://movie.douban.com/subject/1/) | data |\n")
            f.write("| [Movie B](https://movie.douban.com/subject/2/) | data |\n")
            f.write("\n")
            f.write("## 2025-08-15\n\n")
            f.write("| [Movie A](https://movie.douban.com/subject/1/) | data |\n")
            f.write("| [Movie C](https://movie.douban.com/subject/3/) | data |\n")
            temp_path = f.name

        try:
            entries, movies = count_entries_and_movies(temp_path)
            self.assertEqual(entries, 2)
            self.assertEqual(movies, 3)  # Movie A, Movie B, Movie C
        finally:
            os.unlink(temp_path)

    def test_count_old_format(self):
        """测试统计旧格式文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Douban-Movie-250-Diff\n\n")
            f.write("## 2025-03-03\n\n")
            f.write("| [Movie A](https://movie.douban.com/subject/1/) | data |\n")
            f.write("## 2025-02-24\n\n")
            f.write("| [Movie B](https://movie.douban.com/subject/2/) | data |\n")
            temp_path = f.name

        try:
            entries, movies = count_entries_and_movies(temp_path)
            self.assertEqual(entries, 2)
            self.assertEqual(movies, 2)
        finally:
            os.unlink(temp_path)

    def test_count_empty_file(self):
        """测试统计空文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            temp_path = f.name

        try:
            entries, movies = count_entries_and_movies(temp_path)
            self.assertEqual(entries, 0)
            self.assertEqual(movies, 0)
        finally:
            os.unlink(temp_path)


class TestGenerateIndexEntry(unittest.TestCase):
    """测试索引条目生成函数"""

    def setUp(self):
        """创建临时目录和测试文件"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """清理临时目录"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_generate_new_format_entry(self):
        """测试生成新格式索引条目"""
        # 创建新格式文件
        filepath = os.path.join(self.test_dir, "2025-08.md")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("<!-- Archive: 2025-08 -->\n")
            f.write("## 2025-08-30\n\n")
            f.write("| [Movie A](https://movie.douban.com/subject/1/) | data |\n")
            f.write("## 2025-08-01\n\n")
            f.write("| [Movie B](https://movie.douban.com/subject/2/) | data |\n")

        with patch('archive.PATHS', {'archive_dir': self.test_dir}):
            entry = generate_index_entry("2025-08.md", is_new_format=True)

            self.assertEqual(entry['filename'], "2025-08.md")
            self.assertEqual(entry['month'], "2025-08")
            self.assertEqual(entry['first_date'], "2025-08-30")
            self.assertEqual(entry['last_date'], "2025-08-01")
            self.assertEqual(entry['entries'], 2)
            self.assertEqual(entry['movies'], 2)

    def test_generate_old_format_entry(self):
        """测试生成旧格式索引条目"""
        filepath = os.path.join(self.test_dir, "2025-03-03.md")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# Douban-Movie-250-Diff\n\n")
            f.write("## 2025-03-03\n\n")
            f.write("| [Movie A](https://movie.douban.com/subject/1/) | data |\n")

        with patch('archive.PATHS', {'archive_dir': self.test_dir}):
            entry = generate_index_entry("2025-03-03.md", is_new_format=False)

            self.assertEqual(entry['filename'], "2025-03-03.md")
            self.assertEqual(entry['archived_date'], "2025-03-03")
            self.assertEqual(entry['first_date'], "2025-03-03")
            self.assertEqual(entry['entries'], 1)
            self.assertEqual(entry['movies'], 1)


if __name__ == '__main__':
    unittest.main()
