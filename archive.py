import datetime
import os
from common import PATHS, log


# 归档数据
def archive_data():
    today = datetime.date.today()
    with open(PATHS['readme_filename'], 'r', encoding='utf-8') as f_readme:
        lines = f_readme.readlines()
    for i, line in enumerate(lines):
        if line.startswith("## "):
            last_date_string = line.strip().split(" ")[1]
            archive_filename = os.path.join(PATHS['archive_dir'], f"{last_date_string}.md")
            os.makedirs(PATHS['archive_dir'], exist_ok=True)
            with open(archive_filename, 'w', encoding='utf-8') as f_archive:
                f_archive.writelines(lines)
            lines = []
            log("archive data success")
            break
    md_head = "# Douban-Movie-250-Diff\n\n" \
                "A diff log of the Douban top250 movies.\n\n" \
                f"*Updated on {today.isoformat()}*\n\n"
    md_content = f"## {today.isoformat()}\n\n"
    newlines = [md_head, md_content]
    with open(PATHS['readme_filename'], 'w', encoding='utf-8') as f:
        f.writelines(newlines)


if __name__ == "__main__":
    log("archive data start")
    archive_data()