import scrapy
from scrapy.http import Request
import os
import re
from bs4 import BeautifulSoup, Tag
import unicodedata
import random
from urllib.parse import urlparse

class FreewebnovelSpider(scrapy.Spider):
    name = "freewebnovel"
    allowed_domains = [
        "freewebnovel.com",
        "bednovel.com",
        "innread.com",
        "innnovel.com",
        "libread.com",
        "libread.org",
    ]
    start_urls = [
        "https://freewebnovel.com/"
    ]

    def __init__(self, *args, **kwargs):
        super(FreewebnovelSpider, self).__init__(*args, **kwargs)
        # Backward-compatible: allow either target_books or targets
        self.target_books = int(kwargs.get('targets', kwargs.get('target_books', 1)))
        self.scraped_books = 0
        self._seen_novel_urls = set()
        # Optional genre filter (comma-separated). If not provided, use a default list
        raw_genres = kwargs.get('genre', '') or kwargs.get('genres', '')
        parsed = [g.strip() for g in raw_genres.split(',') if g.strip()]
        self.genres = parsed if parsed else [
            'Romance', 'Drama', 'Harem', 'Horror', 'Mecha', 'Smut',
            'Action', 'Fantasy', 'Sci-fi', 'Mystery', 'Adventure'
        ]
        self.max_genre_pages = int(kwargs.get('genre_pages', 5))

    def start_requests(self):
        query = getattr(self, "query", None)
        if query:
            for url in self.start_urls:
                yield scrapy.FormRequest(
                    url=f"{url}search/",
                    formdata={"searchkey": query},
                    callback=self.parse_search_results,
                )
        else:
            # No query: scrape random books from genre pages
            for url in self.start_urls:
                base = url.rstrip('/')
                for genre in self.genres:
                    if self.scraped_books >= self.target_books:
                        break
                    slug = genre.strip().lower()
                    for page in range(1, self.max_genre_pages + 1):
                        if self.scraped_books >= self.target_books:
                            break
                        genre_url = f"{base}/genre/{slug}?page={page}"
                        yield Request(
                            genre_url,
                            callback=self.parse_genre_listing,
                            dont_filter=True,
                            meta={"genre": genre, "page": page},
                        )

    def parse_search_results(self, response):
        for novel in response.css(".col-content .con .txt h3 a"):
            if self.scraped_books >= self.target_books:
                self.crawler.engine.close_spider(self, 'target_books_reached')
                return

            novel_url = response.urljoin(novel.css("::attr(href)").get())
            yield Request(novel_url, callback=self.parse_novel)
            self.scraped_books += 1

    def parse_genre_listing(self, response):
        if self.scraped_books >= self.target_books:
            return
        # Collect novel links with multiple fallbacks
        hrefs = set()
        # Known pattern
        hrefs.update([
            response.urljoin(a.get())
            for a in response.css('.col-content .con .txt h3 a::attr(href)')
        ])
        # Very common listing blocks on freewebnovel clones
        hrefs.update([
            response.urljoin(a.get())
            for a in response.css('.book-mid-info h4 a::attr(href), h3.tit a::attr(href), .bookname a::attr(href), .book-title a::attr(href)')
        ])
        # Common list containers
        hrefs.update([
            response.urljoin(a.get())
            for a in response.css('.book-list a::attr(href), .m-book a::attr(href), .bookshelf a::attr(href)')
        ])
        # Fallback: any link that looks like a novel detail page
        hrefs.update([
            response.urljoin(h)
            for h in response.css('a::attr(href)').getall()
            if '/novel/' in (h or '') and '/chapter/' not in (h or '')
        ])
        hrefs = [h for h in hrefs if h]
        # Keep only novel detail pages; drop any chapter URLs
        filtered = []
        for h in hrefs:
            try:
                path = urlparse(h).path.lower()
            except Exception:
                continue
            if '/novel/' not in path:
                continue
            if 'chapter' in path:
                continue
            filtered.append(h)
        hrefs = filtered
        random.shuffle(hrefs)
        self.logger.info(f"[genre] {response.url} -> found {len(hrefs)} candidate novels (filtered)")
        if not hrefs:
            self.logger.warning(f"[genre] No novel links found on {response.url}")
        for novel_url in hrefs:
            if self.scraped_books >= self.target_books:
                return
            if not novel_url or novel_url in self._seen_novel_urls:
                continue
            self._seen_novel_urls.add(novel_url)
            self.logger.info(f"[genre] Queue novel: {novel_url}")
            yield Request(novel_url, callback=self.parse_novel, dont_filter=True)
            self.scraped_books += 1

    def parse(self, response):
        pass

    def parse_novel(self, response):
        # Title fallbacks
        book_title = (
            response.css(".m-desc h1.tit::text").get()
            or response.css('h1.tit::text').get()
            or response.css('h1::text').get()
            or response.css('meta[property="og:title"]::attr(content)').get()
        )
        if book_title:
            # Sanitize the book title to create a valid directory name
            sane_book_title = "".join(c for c in book_title if c.isalnum() or c in (' ', '.')).rstrip()
            book_dir = os.path.join('output', sane_book_title)
            os.makedirs(book_dir, exist_ok=True)

            # Crawl all chapters across paginated chapter lists
            # Start from the current page (novel page contains first chapter list block)
            yield response.request.replace(
                callback=self.parse_chapter_list,
                dont_filter=True,
                meta={'book_dir': book_dir, 'chapter_counter': 0}
            )
            
            # The image pipeline needs a dictionary with image_urls and the book_dir
            cover_src = response.css(".m-imgtxt img::attr(src)").get()
            if cover_src:
                yield {
                    'image_urls': [response.urljoin(cover_src)],
                    'book_dir': book_dir,
                }

    def parse_chapters(self, response):
        chapters = []
        # Primary known pattern
        for chapter in response.css("#idData li > a"):
            chapters.append({
                "title": chapter.css("::text").get(),
                "url": response.urljoin(chapter.css("::attr(href)").get()),
            })
        # Fallback patterns
        if not chapters:
            for sel in [
                '.chapter-list a',
                '.m-newchpter a',
                'ul#idData a',
                'div.chapter a',
                'a[href*="/chapter/"]',
            ]:
                links = response.css(f'{sel}::attr(href)').getall()
                if links:
                    for href in links:
                        chapters.append({
                            "title": None,
                            "url": response.urljoin(href),
                        })
                    break
        # De-duplicate and keep order
        seen = set()
        ordered = []
        for ch in chapters:
            u = ch.get('url')
            if u and u not in seen:
                seen.add(u)
                ordered.append(ch)
        return ordered

    def parse_chapter_list(self, response):
        book_dir = response.meta['book_dir']
        chapter_counter = int(response.meta.get('chapter_counter', 0))

        # Collect chapter links on this page (with fallbacks)
        chapter_links = [
            response.urljoin(a.css("::attr(href)").get())
            for a in response.css("#idData li > a")
        ]
        if not chapter_links:
            for sel in [
                '.chapter-list a::attr(href)',
                '.m-newchpter a::attr(href)',
                'ul#idData a::attr(href)',
                'div.chapter a::attr(href)',
                'a[href*="/chapter/"]::attr(href)'
            ]:
                links = response.css(sel).getall()
                if links:
                    chapter_links = [response.urljoin(h) for h in links]
                    break
        # Many sites list newest first; reverse to write from earliest to latest
        chapter_links = [link for link in chapter_links if link]
        chapter_links.reverse()

        for link in chapter_links:
            chapter_counter += 1
            yield Request(
                url=link,
                callback=self.parse_chapter_content,
                dont_filter=True,
                meta={'book_dir': book_dir, 'chapter_num': chapter_counter}
            )

        # Find pagination next link for chapter list
        next_href = (
            response.css('.pages a.next::attr(href)').get()
            or response.css('.page a.next::attr(href)').get()
            or response.css('a.next::attr(href)').get()
        )
        if next_href and self.scraped_books >= 0:
            next_url = response.urljoin(next_href)
            yield Request(
                next_url,
                callback=self.parse_chapter_list,
                dont_filter=True,
                meta={'book_dir': book_dir, 'chapter_counter': chapter_counter}
            )

    def parse_chapter_content(self, response):
        book_dir = response.meta['book_dir']
        chapter_num = response.meta['chapter_num']
        
        # Logic from the original lncrawl's select_chapter_body and normalize_text
        body_tag = response.css(".m-read .txt")
        has_promo = response.xpath("//style[contains(text(), 'p:nth-last-child')]" ).get()
        
        if body_tag:
            # Normalize text
            text = "".join(body_tag.getall())
            text = unicodedata.normalize("NFKC", text)
            soup = BeautifulSoup(text, "html.parser")

            if has_promo:
                match = re.search(r'p:nth-last-child\((\d)\)', has_promo)
                if match:
                    idx = int(match.group(1))
                    # Remove the promo paragraph
                    promo_p = soup.find_all("p")
                    if len(promo_p) >= idx:
                        promo_p[-idx].decompose()

            # Clean up bad tags
            for tag in soup.find_all(['h4', 'sub']):
                tag.decompose()

            chapter_text = soup.get_text(separator='\n', strip=True)
            
            # Remove bad text pairs
            bad_texts = [
                r"freewebnovel\.com",
                r"innread\.com",
                r"bednovel\.com",
                r"Updates by Freewebnovel\. com",
                r"” Search Freewebnovel\.com\. on google”\.",
                r"\/ Please Keep reading on MYFreeWebNovel\.C0M",
                r"please keep reading on Freewebnovel\(dot\)C0M",
                r"Continue\_reading on Freewebnovel\.com",
                r"Continue \-reading on Freewebnovel\.com",
                r"\/ Please Keep reading 0n FreewebNOVEL\.C0M",
                r"\[ Follow current novels on Freewebnovel\.com \]",
                r"‘Freewebnovel\.com\*’",
                r"‘Search Freewebnovel\.com\, on google’",
                r"‘ Search Freewebnovel\.com\(\) ‘",
                r"“Freewebnovel\.com \.”",
                r"“Please reading on Freewebnovel\.com\.”",
                r"“Search Freewebnovel\.com\. on google”",
                r"“Read more on Freewebnovel\.com\. org”",
                r"Thank you for reading on FreeWebNovel\.me",
                r"Please reading \-on Freewebnovel\.com",
                r"”Search \(Freewebnovel\.com\(\) on google\”\?",
                r"“Please reading on Freewebnovel\.com \:"
                r"”Please reading on Freewebnovel\.com\.”\?",
                r"“Please reading on Freewebnovel\.com\&gt\; ”\""
            ]
            for bad_text in bad_texts:
                chapter_text = re.sub(bad_text, '', chapter_text)

            chapter_filename = os.path.join(book_dir, f"Chapter-{chapter_num}.txt")
            with open(chapter_filename, 'w', encoding='utf-8') as f:
                f.write(chapter_text)
