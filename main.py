import argparse
import json
from datetime import datetime
from typing import Any, Dict, List
from src.spider import MovieSpider
from src.diff_processor import DiffProcessor
from src.common import log


REQUIRED_MOVIE_FIELDS = {'rank', 'pic', 'name', 'link', 'score', 'id'}


def load_mock_movies(file_path: str) -> List[Dict[str, Any]]:
    """从本地 JSON 文件加载 mock 电影列表。"""
    with open(file_path, 'r', encoding='utf-8') as f:
        movies = json.load(f)

    if not isinstance(movies, list):
        raise ValueError("Mock movie data must be a JSON array")

    for index, movie in enumerate(movies, start=1):
        if not isinstance(movie, dict):
            raise ValueError(f"Mock movie #{index} must be an object")

        missing_fields = REQUIRED_MOVIE_FIELDS - set(movie.keys())
        if missing_fields:
            fields = ", ".join(sorted(missing_fields))
            raise ValueError(f"Mock movie #{index} missing required fields: {fields}")

    return movies


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run Douban Top250 diff monitor")
    parser.add_argument(
        '--mock',
        dest='mock_file',
        help='Load latest movies from a local mock JSON file instead of fetching Douban'
    )
    parser.add_argument(
        '--state-file',
        help='Override the recent movie state JSON file, useful for local mock tests'
    )
    parser.add_argument(
        '--readme-file',
        help='Override the README output file, useful for local mock tests'
    )
    return parser.parse_args(argv)


def run(argv=None):
    """运行豆瓣电影Top250变更监控"""
    args = parse_args(argv)
    startTime = datetime.now()
    try:
        if args.mock_file:
            log(f"Loading mock movie data from {args.mock_file}")
            latest_movies = load_mock_movies(args.mock_file)
        else:
            # 爬取最新电影列表
            spider = MovieSpider()
            latest_movies = spider.fetch_movie_list()
        
        # 处理电影列表差异
        processor = DiffProcessor(
            movie_list_file=args.state_file,
            readme_file=args.readme_file
        )
        processor.process_diff(latest_movies)
        
    except Exception as e:
        log(f"Error running movie diff: {str(e)}")
    finally:
        time_cost = (datetime.now() - startTime).total_seconds()
        log(f"Time cost: {time_cost}s")

if __name__ == "__main__":
    run()
