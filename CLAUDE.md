# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project monitors and tracks changes to the Douban (Chinese movie rating platform) Top 250 movies list. It scrapes the latest rankings, compares them with the previous version, and generates a diff log in the README. The project runs automatically via GitHub Actions.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the main scraper and diff processor
python main.py

# Run the monthly archive script
python archive.py

# Run tests
python -m unittest discover -s test
# Run a specific test file
python -m unittest test.test_spider
```

## Architecture

The project follows a simple pipeline architecture:

1. **MovieSpider** (`src/spider.py`): Fetches and parses Douban Top 250 pages
   - Fetches 10 pages (25 movies per page = 250 total)
   - Implements retry logic (3 attempts with 2s interval)
   - Rate-limited with 1s delay between requests
   - Returns list of movie dicts with keys: `rank`, `pic`, `name`, `link`, `score`, `id`

2. **DiffProcessor** (`src/diff_processor.py`): Compares versions and updates documentation
   - Loads previous state from `recently_movie_250.json`
   - Compares by movie ID to detect: new entries, removed entries, rank/score changes
   - Updates README.md with formatted markdown tables
   - Saves latest state to JSON for next comparison

3. **Archive script** (`archive.py`): Monthly maintenance
   - Moves previous month's README content to `archive/YYYY-MM-DD.md`
   - Resets README with new date header

## Key Files

- `src/common.py`: Shared configuration (PATHS, HEADERS, REQUEST_CONFIG) and utilities (log, write_text)
- `recently_movie_250.json`: Persistent state file storing the last fetched movie list
- `README.md`: Main output file with diff logs in markdown tables
- `archive/`: Monthly archives of previous diff logs

## GitHub Actions

Two workflows handle automation:

1. `.github/workflows/actions.yml`: Runs daily at 12:00 UTC - executes `main.py`
2. `.github/workflows/run_archive.yml`: Runs monthly on the 1st at 10:00 UTC - executes `archive.py`

Both workflows auto-commit changes with "Auto updated" or "Auto archived." messages.

## Testing

Tests are in `test/test_spider.py` using unittest. Key test scenarios:
- Request failures and retry logic
- Non-200 status codes
- Invalid HTML parsing
- Missing data in movie items
- Partial page failures

## Code Notes

- The spider uses BeautifulSoup for HTML parsing and targets Douban's specific CSS classes (`grid_view`, `item`, `pic`, `info`, etc.)
- Movie IDs are extracted from the URL path (last segment after splitting by '/')
- Rate limiting is important to avoid being blocked by Douban
- README format: Header with update date, followed by dated sections (## YYYY-MM-DD) with markdown tables for changes
