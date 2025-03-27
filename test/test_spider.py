import unittest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup
from src.spider import MovieSpider
from requests.exceptions import RequestException

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
        # 测试无效HTML结构
        invalid_html = '<html><body>Invalid structure</body></html>'
        
        with self.assertRaises(AttributeError):
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