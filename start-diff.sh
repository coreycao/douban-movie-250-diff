# Add crontab task to run this shell, or set GitHub Action to run the python script.

#0 23 * * * nohup sh /Users/corey/development/playground/py_playground/Movie-250-Diff/start.sh >> /Users/corey/development/playground/py_playground/log/Movie-250-Diff.log 2>&1 &

echo -e "\n----------Start time:----------"
date

cd /Users/corey/development/playground/py_playground/Movie-250-Diff
git pull
pipenv run python main.py
git add .
today=`date +"%Y-%m-%d"`
git commit -m "auto update $today"
git push origin main