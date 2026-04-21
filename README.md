# PAMOR Scraper

Simple scraper for landslide events (`Tanah Longsor`) from PAMOR DIY and export to CSV.

## Quick start

1. Install dependencies:
   - `pip install requests beautifulsoup4 pandas`
2. Run scraper:
   - `python scraper.py`
3. Output file:
   - `kejadian_clean.csv`

## What it does

- Gets list data from PAMOR (`data_kejadian`)
- Opens each detail page
- Extracts key fields including `latitude`, `longitude`, `tanggal`, and `jam`
- Cleans text values and saves a ready-to-use CSV

## Notes

- Current date range is set inside `scraper.py`
- You can edit the year/date filter in `main()` as needed
