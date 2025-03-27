from datetime import datetime
from src.spider import MovieSpider
from src.diff_processor import DiffProcessor
from src.common import log


def run():
    """运行豆瓣电影Top250变更监控"""
    startTime = datetime.now()
    try:
        # 爬取最新电影列表
        spider = MovieSpider()
        latest_movies = spider.fetch_movie_list()
        
        # 处理电影列表差异
        processor = DiffProcessor()
        processor.process_diff(latest_movies)
        
    except Exception as e:
        log(f"Error running movie diff: {str(e)}")
    finally:
        time_cost = (datetime.now() - startTime).total_seconds()
        log(f"Time cost: {time_cost}s")

if __name__ == "__main__":
    run()