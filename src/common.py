import random


PATHS = {
    'movie_list_filename': "recently_movie_250.json",
    'readme_filename': "README.md",
    'archive_dir': "archive"
}


# User-Agent 轮换池，模拟不同浏览器和操作系统
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
]

HEADERS_TEMPLATE = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
    'Referer': 'https://movie.douban.com/top250'
}


def get_headers():
    """生成随机请求头，防止被识别为爬虫"""
    headers = HEADERS_TEMPLATE.copy()
    headers['User-Agent'] = random.choice(USER_AGENTS)
    return headers


REQUEST_CONFIG = {
    'url_douban_top250': 'https://movie.douban.com/top250',
    'request_timeout': 10,
    'page_size': 25,
    'total_size': 250,
    'min_delay': 2,  # 最小延迟（秒）
    'max_delay': 5,  # 最大延迟（秒）
    'rate_limit': 0.3  # 每秒最大请求数
}


def log(*args):
    print("Movie250Diff: ", *args)


def write_text(file_name, method, text):
    """
    method: 'a'-append,
            'w'-overwrite
    """
    with open(file_name, method, encoding='utf-8') as f:
        f.write(text)

