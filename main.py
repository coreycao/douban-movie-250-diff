# A simple spider that diff the Douban's top-250 movies

import datetime
import requests
import json
from bs4 import BeautifulSoup
from common import HEADERS, PATHS, REQUEST_CONFIG, log, write_text


movie_list = []


def fetch_movie_list():
    for i in range(0, REQUEST_CONFIG['total_size'], REQUEST_CONFIG['page_size']):
        params = {
            'start': str(i),
            'filter': ''
        }
        page_num = i / 25 + 1
        response = requests.get(REQUEST_CONFIG['url_douban_top250'], params=params, headers=HEADERS, timeout=REQUEST_CONFIG['request_timeout'])
        log("request start, page_num: ", page_num)
        if i == 0 and response.status_code != 200:
            log("request failed, status_code: ", response.status_code)
            raise RuntimeError("request failed")
        log("request success, page_num: ", page_num)
        log("parse html start, page_num: ", page_num)
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.find('ol', class_='grid_view').find_all('div', class_='item')
        for item in items:
            movie = parse_movie_item(item)
            movie_list.append(movie)
        log("parse html success, page_num: ", page_num)
    log("parse data end")


def parse_movie_item(item):
    movie = {}

    item_pic = item.find('div', class_='pic')
    movie_rank = item_pic.em.text.strip()
    movie_pic = item_pic.a.img['src']

    item_info = item.find('div', class_='info').find('div', class_='hd')
    movie_link = item_info.a['href']
    movie_name = item_info.a.span.text.strip()
    movie_score = item.find('div', class_='info').find('div', class_='bd').find('span', class_='rating_num').text

    movie['rank'] = movie_rank
    movie['pic'] = movie_pic
    movie['name'] = movie_name
    movie_link = movie_link.strip('/')
    movie['link'] = movie_link
    movie['score'] = movie_score
    split_link = movie_link.split('/')
    movie_id = split_link[len(split_link) - 1]
    movie['id'] = movie_id
    return movie


def diff_movie_list():
    today = datetime.date.today()
    try:
        with open(PATHS['movie_list_filename']) as f:
            movie_list_recently = json.load(f)
        log("load recent movie list, prepare to diff")
        movie_dict_recently = {movie['id']: movie for movie in movie_list_recently}
        movie_dict_latest = {movie['id']: movie for movie in movie_list}

        movie_set_recently = set(movie_dict_recently.keys())
        movie_set_latest = set(movie_dict_latest.keys())

        movie_outdated_set = movie_set_recently - movie_set_latest
        movie_updated_set = movie_set_latest - movie_set_recently

        movie_changed = []
        for idx, item_old in movie_dict_recently.items():
            if idx in movie_dict_latest:
                item_latest = movie_dict_latest[idx]
                if item_old['rank'] != item_latest['rank'] or item_old['score'] != item_latest['score']:
                    movie_changed.append([item_old, item_latest])

        # 如果数据未发生变化，则不做任何操作
        if len(movie_outdated_set) == 0 and len(movie_changed) == 0:
            log("No changes.")
        else:
            # 更新 README.md 文件
            md_head = "# Douban-Movie-250-Diff\n\n" \
                        "A diff log of the Douban top250 movies.\n\n" \
                        f"*Updated on {today.isoformat()}*\n\n"
            md_content = f"## {today.isoformat()}\n\n"
            if len(movie_outdated_set) != 0:
                log("Rank list changed")
                log("updated movies: ", movie_updated_set)
                log("outdated movies: ", movie_outdated_set)
                md_updated = "#### 新上榜电影\n\n"
                table_head = "|   Rank  |     Name     |   Score  |\n| ------- | ------------ | -------- |\n"
                md_updated += table_head
                for item in iter(movie_updated_set):
                    movie = movie_dict_latest[item]
                    md_updated += "| {rank} | [{name}]({link}) | {score} |\n" \
                        .format(rank=movie['rank'], name=movie['name'], link=movie['link'], score=movie['score'])
                md_updated += "\n#### 退出榜单电影\n\n"
                md_updated += table_head
                for item in iter(movie_outdated_set):
                    movie = movie_dict_recently[item]
                    md_updated += "| {rank} | [{name}]({link}) | {score} |\n" \
                        .format(rank=movie['rank'], name=movie['name'], link=movie['link'], score=movie['score'])
                md_content += md_updated
            if len(movie_changed) != 0:
                log("Rank or score changed.")
                md_changed = "\n#### 排名及分数变化\n\n"
                table_head = "|     Name    |   Rank   |   Score  |\n| ------- | ------------ | -------- |\n"
                md_changed += table_head
                for item in movie_changed:
                    movie_old = item[0]
                    movie_latest = item[1]
                    diff_rank = movie_old['rank'] if movie_old['rank'] == movie_latest['rank'] \
                        else (movie_old['rank'] + "➡️" + movie_latest['rank'])
                    diff_score = movie_old['score'] if movie_old['score'] == movie_latest['score'] \
                        else (movie_old['score'] + "➡️" + movie_latest['score'])
                    md_changed += "| [{name}]({link}) | {rank_diff} | {score_diff} |\n" \
                        .format(name=movie_old['name'], link=movie_old['link'],
                                rank_diff=diff_rank, score_diff=diff_score, )
                md_content += md_changed

                with open(PATHS['readme_filename'], 'r+', encoding='utf-8') as f:
                    lines = f.readlines()
                    f.seek(0)
                    f.truncate()
                    f.writelines(md_head + md_content)
                    f.writelines(lines[6:])
        with open(PATHS['movie_list_filename'], 'w', encoding='utf-8') as f:
            json.dump(movie_list, f, ensure_ascii=False, indent=2)
    except IOError:
        log("load recent movie list fail, dump latest data.")
        with open(PATHS['movie_list_filename'], 'w', encoding='utf-8') as f:
            json.dump(movie_list, f, ensure_ascii=False, indent=2)

        md_head = "# Douban-Movie-250-Diff\n\n" \
                  "A diff log of the Douban top250 movies.\n" \
                  f"*Updated on {today.isoformat()}*\n\n"
        write_text(PATHS['readme_filename'], 'w', md_head)


if __name__ == "__main__":
    t1 = datetime.datetime.now()
    try:
        fetch_movie_list()
    except requests.exceptions.RequestException as e:
        log(f"request err: {str(e)}")
    except json.JSONDecodeError as e:
        log(f"JSON parse err: {str(e)}")
    except Exception as e:
        log(f"unknown err: {str(e)}")
    else:
        diff_movie_list()
    log("Time cost: {}s.".format((datetime.datetime.now() - t1).total_seconds()))