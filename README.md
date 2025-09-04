# FreeWebNovel Scraper 🕷️

A Scrapy-based web crawler that downloads novels from freewebnovel.com. It scrapes book covers and chapter contents into organized text files. Because manually copying chapters is for suckers.

## Setup

1. Clone this repo
2. Install requirements:  
   ```bash
   pip install scrapy pillow beautifulsoup4 lxml
   ```
3. Run the spider (see examples below)

## Usage

Scrape a specific number of books from search results:

```bash
scrapy crawl freewebnovel -a query="My Vampire System"
```

Scrape random books from specific genres (comma-separated list supported):

```bash
scrapy crawl freewebnovel -a targets=20 -a genre=Romance
scrapy crawl freewebnovel -a targets=50 -a genre=Harem
```

Genre examples: Harem, Romance, Smut, Action

## Output 

Books are saved in `output/BookTitle/` with:
- `Chapter-X.txt` files for each chapter
- Book cover image in the same directory

## Configuration

Modify `freewebnovel_scraper/settings.py` to adjust:
- Download delays
- Concurrent requests
- Image storage settings

# Roadmap for the future.
- Well, I don't really have any "roadmap" for this side project.
- If I'm bored enough in the future, well, then updates may come, extending support to other novel sites or manga reading sites. For now, it only supports freewebnovel.
- If ya'll want, you can contribute to this side project, I may not really notice it though, since I don't use GitHub that much.

## Disclaimer ⚠️

This is for educational purposes only. Use strictly only on books you have authorization for. DO NOT USE IT ON BOOKS YOU DO NOT HAVE PERMISSION FOR.
The author will NOT be responsible if you ignore the warnings. 
