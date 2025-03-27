PATHS = {
    'movie_list_filename': "recently_movie_250.json",
    'readme_filename': "README.md",
    'archive_dir': "archive"
}


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4343.0 Safari/537.36',
    'Referer': 'https://movie.douban.com/top250'
}


REQUEST_CONFIG = {
    'url_douban_top250' : 'https://movie.douban.com/top250',
    'request_timeout' : 10,
    'page_size': 25,
    'total_size':250
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

