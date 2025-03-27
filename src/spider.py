import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from time import sleep
from src.common import log, REQUEST_CONFIG, HEADERS


class MovieSpider:
    def __init__(self):
        self.url = REQUEST_CONFIG['url_douban_top250']
        self.timeout = REQUEST_CONFIG['request_timeout']
        self.page_size = REQUEST_CONFIG['page_size']
        self.total_size = REQUEST_CONFIG['total_size']
        self.retry_times = 3
        self.retry_interval = 2

    def fetch_movie_list(self) -> List[Dict[str, Any]]:
        """获取豆瓣Top250电影列表"""
        movie_list = []
        try:
            for i in range(0, self.total_size, self.page_size):
                page_num = i // self.page_size + 1
                movies = self._fetch_page(i, page_num)
                if movies:
                    movie_list.extend(movies)
                sleep(1)  # 请求限速
            return movie_list
        except Exception as e:
            log(f"Error occurred while fetching movie list: {str(e)}")
            raise

    def _fetch_page(self, start: int, page_num: int) -> List[Dict[str, Any]]:
        """获取单页电影数据"""
        params = {'start': str(start), 'filter': ''}
        last_error = None
        for _ in range(self.retry_times):
            try:
                log(f"Fetching page {page_num}...")
                response = requests.get(
                    self.url,
                    params=params,
                    headers=HEADERS,
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    return self._parse_page(response.text)
                last_error = f"Request failed with status code: {response.status_code}"
                log(last_error)
            except requests.RequestException as e:
                last_error = f"Request error on page {page_num}: {str(e)}"
                log(last_error)
            sleep(self.retry_interval)
        raise RuntimeError(f"Failed to fetch page {page_num} after {self.retry_times} retries. Last error: {last_error}")

    def _parse_page(self, html: str) -> List[Dict[str, Any]]:
        """解析页面HTML"""
        movies = []
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.find('ol', class_='grid_view').find_all('div', class_='item')
        
        for item in items:
            movie = self._parse_movie_item(item)
            movies.append(movie)
        return movies

    def _parse_movie_item(self, item: BeautifulSoup) -> Dict[str, Any]:
        """解析单个电影数据"""
        item_pic = item.find('div', class_='pic')
        item_info = item.find('div', class_='info').find('div', class_='hd')
        movie_link = item_info.a['href'].strip('/')
        
        return {
            'rank': item_pic.em.text.strip(),
            'pic': item_pic.a.img['src'],
            'name': item_info.a.span.text.strip(),
            'link': movie_link,
            'score': item.find('div', class_='info').find('div', class_='bd')
                        .find('span', class_='rating_num').text,
            'id': movie_link.split('/')[-1]
        }