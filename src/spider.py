import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from time import sleep, time
import random
from threading import Lock
from src.common import log, REQUEST_CONFIG, get_headers


class RateLimiter:
    """令牌桶算法实现的限频器，防止请求过于频繁被识别"""

    def __init__(self, rate: float, capacity: int = 5):
        """
        Args:
            rate: 每秒生成的令牌数（每秒允许的请求数）
            capacity: 令牌桶容量（允许的突发请求数）
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_time = time()
        self.lock = Lock()

    def acquire(self):
        """获取一个令牌，如果令牌不足则等待"""
        with self.lock:
            now = time()
            elapsed = now - self.last_time
            # 计算新生成的令牌数
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_time = now

            if self.tokens < 1:
                # 令牌不足，计算等待时间
                wait_time = (1 - self.tokens) / self.rate
                sleep(wait_time)
                self.tokens = 0
            else:
                # 消耗一个令牌
                self.tokens -= 1


class MovieSpider:
    def __init__(self):
        self.url = REQUEST_CONFIG['url_douban_top250']
        self.timeout = REQUEST_CONFIG['request_timeout']
        self.page_size = REQUEST_CONFIG['page_size']
        self.total_size = REQUEST_CONFIG['total_size']
        self.min_delay = REQUEST_CONFIG['min_delay']
        self.max_delay = REQUEST_CONFIG['max_delay']
        self.retry_times = 3
        self.retry_interval = 2
        # 初始化限频器
        self.rate_limiter = RateLimiter(
            rate=REQUEST_CONFIG['rate_limit'],
            capacity=3
        )

    def fetch_movie_list(self) -> List[Dict[str, Any]]:
        """获取豆瓣Top250电影列表"""
        movie_list = []
        try:
            for i in range(0, self.total_size, self.page_size):
                page_num = i // self.page_size + 1
                movies = self._fetch_page(i, page_num)
                if movies:
                    movie_list.extend(movies)
                # 随机延迟，模拟人类行为（2-5秒之间）
                if i + self.page_size < self.total_size:  # 最后一次请求不需要延迟
                    delay = random.uniform(self.min_delay, self.max_delay)
                    log(f"Waiting {delay:.2f}s before next request...")
                    sleep(delay)
            return movie_list
        except Exception as e:
            log(f"Error occurred while fetching movie list: {str(e)}")
            raise

    def _fetch_page(self, start: int, page_num: int) -> List[Dict[str, Any]]:
        """获取单页电影数据"""
        params = {'start': str(start), 'filter': ''}
        last_error = None
        for attempt in range(self.retry_times):
            try:
                # 通过限频器控制请求速率
                self.rate_limiter.acquire()
                log(f"Fetching page {page_num}... (attempt {attempt + 1}/{self.retry_times})")
                response = requests.get(
                    self.url,
                    params=params,
                    headers=get_headers(),  # 使用随机 User-Agent
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    return self._parse_page(response.text)
                last_error = f"Request failed with status code: {response.status_code}"
                log(last_error)
            except requests.RequestException as e:
                last_error = f"Request error on page {page_num}: {str(e)}"
                log(last_error)
            # 退避重试：每次重试间隔递增
            if attempt < self.retry_times - 1:
                sleep(self.retry_interval * (attempt + 1))
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