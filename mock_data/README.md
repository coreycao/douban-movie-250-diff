# Mock Data

Local fixtures for testing the diff pipeline without fetching Douban.

Run a mock diff into temporary output files:

```bash
tmp_dir="$(mktemp -d)"
cp mock_data/recently_movie_250.json "$tmp_dir/recently_movie_250.json"
cp README.md "$tmp_dir/README.md"
python main.py \
  --mock mock_data/latest_movie_250.json \
  --state-file "$tmp_dir/recently_movie_250.json" \
  --readme-file "$tmp_dir/README.md"
```

Inspect the generated mock output:

```bash
cat "$tmp_dir/README.md"
```
