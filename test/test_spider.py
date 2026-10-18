import unittest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup
from src.spider import MovieSpider
from requests.exceptions import RequestException

def make_movie(rank, movie_id=None):
    """构造一条符合 spider 输出结构的电影记录"""
    return {
        'rank': str(rank),
        'pic': f'https://img.example.com/p{rank}.webp',
        'name': f'Movie {rank}',
        'link': f'https://movie.douban.com/subject/{movie_id or (1000000 + rank)}',
        'score': '9.0',
        'id': str(movie_id or (1000000 + rank)),
    }

class TestMovieListValidation(unittest.TestCase):
    """测试抓取结果完整性校验：不完整的抓取绝不能参与 diff"""

    def setUp(self):
        self.spider = MovieSpider()

    def test_validate_accepts_full_list(self):
        movies = [make_movie(r) for r in range(1, 251)]
        self.spider._validate_movie_list(movies)  # 不抛错即通过

    def test_validate_rejects_incomplete_fetch(self):
        movies = [make_movie(r) for r in range(1, 250)]  # 只有 249 条
        with self.assertRaises(RuntimeError) as ctx:
            self.spider._validate_movie_list(movies)
        self.assertIn('Incomplete fetch', str(ctx.exception))

    def test_validate_rejects_duplicate_ranks(self):
        movies = [make_movie(r) for r in range(1, 251)]
        movies[10]['rank'] = '1'  # 与首条重复
        with self.assertRaises(RuntimeError) as ctx:
            self.spider._validate_movie_list(movies)
        self.assertIn('rank sequence', str(ctx.exception))

    def test_validate_rejects_non_sequential_ranks(self):
        movies = [make_movie(r) for r in range(1, 251)]
        movies[-1]['rank'] = '251'  # 出现缺号
        with self.assertRaises(RuntimeError):
            self.spider._validate_movie_list(movies)

    def test_validate_rejects_duplicate_ids(self):
        movies = [make_movie(r) for r in range(1, 251)]
        movies[1]['id'] = movies[0]['id']
        with self.assertRaises(RuntimeError) as ctx:
            self.spider._validate_movie_list(movies)
        self.assertIn('Duplicate movie ids', str(ctx.exception))

    def test_validate_rejects_invalid_rank_value(self):
        movies = [make_movie(r) for r in range(1, 251)]
        movies[5]['rank'] = 'abc'
        with self.assertRaises(RuntimeError) as ctx:
            self.spider._validate_movie_list(movies)
        self.assertIn('Invalid rank value', str(ctx.exception))

    @patch('src.spider.sleep')  # 跳过页间延迟，保持测试快速
    @patch.object(MovieSpider, '_fetch_page')
    def test_fetch_movie_list_validates_before_return(self, mock_fetch_page, _mock_sleep):
        """fetch_movie_list 返回前必须通过完整性校验"""
        page = [make_movie(r) for r in range(1, 26)]
        mock_fetch_page.return_value = page
        with self.assertRaises(RuntimeError):  # 25 条 != 250 条
            self.spider.fetch_movie_list()

class TestMovieSpider(unittest.TestCase):
    def setUp(self):
        self.spider = MovieSpider()

    @patch('requests.get')
    def test_fetch_page_request_failure(self, mock_get):
        # 模拟请求失败场景
        mock_get.side_effect = RequestException('Connection error')
        
        with self.assertRaises(RuntimeError) as context:
            self.spider._fetch_page(0, 1)
        
        self.assertIn('Failed to fetch page 1 after 3 retries', str(context.exception))
        self.assertEqual(mock_get.call_count, 3)  # 确认重试3次

    @patch('requests.get')
    def test_fetch_page_bad_status(self, mock_get):
        # 模拟非200状态码响应
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response
        
        with self.assertRaises(RuntimeError) as context:
            self.spider._fetch_page(0, 1)
        
        self.assertIn('Failed to fetch page 1 after 3 retries', str(context.exception))
        self.assertIn('status code: 403', str(context.exception))

    def test_parse_page_invalid_html(self):
        # 测试无效HTML结构（无 grid_view，应抛出 ValueError）
        invalid_html = '<html><body>Invalid structure</body></html>'

        with self.assertRaises(ValueError):
            self.spider._parse_page(invalid_html)

    def test_parse_movie_item_missing_data(self):
        # 测试缺失数据的电影项
        invalid_item = BeautifulSoup('<div class="item"></div>', 'html.parser')
        
        with self.assertRaises(AttributeError):
            self.spider._parse_movie_item(invalid_item)

    @patch('requests.get')
    def test_fetch_movie_list_partial_failure(self, mock_get):
        # 模拟部分页面获取失败
        def mock_response(*args, **kwargs):
            start = int(kwargs['params']['start'])
            if start == 0:
                response = MagicMock()
                response.status_code = 200
                response.text = '<html><ol class="grid_view"></ol></html>'
                return response
            raise RequestException('Connection error')
        
        mock_get.side_effect = mock_response
        
        with self.assertRaises(Exception):
            self.spider.fetch_movie_list()

if __name__ == '__main__':
    unittest.main()