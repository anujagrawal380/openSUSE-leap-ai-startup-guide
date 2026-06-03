"""
Documentation scraper for openSUSE official docs.

Crawls the openSUSE documentation site, extracts clean text content,
and prepares it for ingestion into the RAG pipeline.
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from opensuse_ai.config import DocumentationSource

logger = logging.getLogger(__name__)


@dataclass
class ScrapedPage:
    """A single scraped documentation page."""

    url: str
    title: str
    content: str
    section: str = ""


class DocumentationScraper:
    """
    Crawls openSUSE documentation pages and extracts structured text.

    Respects rate limits and stays within the configured domain boundary.
    """

    def __init__(self, source: DocumentationSource, output_dir: Path):
        self.source = source
        self.output_dir = output_dir
        self.visited: set[str] = set()
        self.pages: list[ScrapedPage] = []
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "openSUSE-AI-Onboarding-Scraper/0.1 (GSoC POC)"
        })

    def scrape(self) -> list[ScrapedPage]:
        """Run the scraper across all start URLs."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        for start_url in self.source.start_urls:
            self._crawl(start_url, depth=0, max_depth=3)

        logger.info(
            "Scraped %d pages from '%s'", len(self.pages), self.source.name
        )
        self._save_pages()
        return self.pages

    def _crawl(self, url: str, depth: int, max_depth: int) -> None:
        """Recursively crawl pages up to max_depth."""
        if url in self.visited:
            return
        if len(self.visited) >= self.source.max_pages:
            return
        if depth > max_depth:
            return

        # Stay within the base domain
        if not url.startswith(self.source.base_url):
            return

        self.visited.add(url)

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("Failed to fetch %s: %s", url, e)
            return

        soup = BeautifulSoup(resp.text, "html.parser")

        page = self._extract_content(url, soup)
        if page and len(page.content.strip()) > 100:
            self.pages.append(page)
            logger.debug("Scraped: %s (%d chars)", page.title, len(page.content))

        # Follow links within the documentation
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Strip fragment
            href = href.split("#")[0]
            if not href:
                continue
            next_url = urljoin(url, href)
            # Only follow HTML pages under the same path prefix
            parsed = urlparse(next_url)
            if parsed.scheme in ("http", "https"):
                self._crawl(next_url, depth + 1, max_depth)

        # Be polite
        time.sleep(0.3)

    def _extract_content(self, url: str, soup: BeautifulSoup) -> ScrapedPage | None:
        """Extract clean text content from an HTML page."""
        # Remove navigation, scripts, styles
        for tag in soup.find_all(["nav", "script", "style", "header", "footer"]):
            tag.decompose()

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else url

        # openSUSE docs typically use <div id="content"> or <div class="book">
        content_div = (
            soup.find("div", {"id": "content"})
            or soup.find("div", {"class": "book"})
            or soup.find("div", {"id": "_content"})
            or soup.find("main")
            or soup.find("article")
            or soup.find("body")
        )

        if content_div is None:
            return None

        # Extract section headers for metadata
        section = ""
        h1 = content_div.find("h1")
        if h1:
            section = h1.get_text(strip=True)

        # Get clean text
        text = content_div.get_text(separator="\n", strip=True)
        # Collapse excessive whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        content = "\n".join(lines)

        return ScrapedPage(url=url, title=title, content=content, section=section)

    def _save_pages(self) -> None:
        """Persist scraped pages as plain text files for transparency."""
        for i, page in enumerate(self.pages):
            safe_name = (
                urlparse(page.url).path.replace("/", "_").strip("_") or f"page_{i}"
            )
            filepath = self.output_dir / f"{safe_name}.txt"
            filepath.write_text(
                f"URL: {page.url}\nTitle: {page.title}\nSection: {page.section}\n\n"
                f"{page.content}",
                encoding="utf-8",
            )


class MediaWikiScraper:
    """
    Fetches a curated list of wiki pages through the MediaWiki API.

    en.opensuse.org blocks plain HTML scraping (403), but its MediaWiki
    API is open — ``action=parse`` returns the rendered page HTML which
    is then cleaned the same way as the crawled docs.
    """

    def __init__(self, source: DocumentationSource, output_dir: Path):
        self.source = source
        self.output_dir = output_dir
        self.pages: list[ScrapedPage] = []
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "openSUSE-AI-Onboarding-Scraper/0.1 (GSoC POC)"
        })

    def scrape(self) -> list[ScrapedPage]:
        """Fetch all configured wiki pages."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        wiki_root = self.source.base_url.rsplit("/", 1)[0]  # strip /api.php

        for page_name in self.source.pages:
            try:
                resp = self.session.get(
                    self.source.base_url,
                    params={
                        "action": "parse",
                        "page": page_name,
                        "format": "json",
                        "prop": "text|displaytitle",
                        "redirects": 1,
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
            except (requests.RequestException, ValueError) as e:
                logger.warning("Failed to fetch wiki page %s: %s", page_name, e)
                continue

            if "error" in data:
                logger.warning(
                    "Wiki page %s: %s", page_name, data["error"].get("info", "error")
                )
                continue

            html = data.get("parse", {}).get("text", {}).get("*", "")
            title = data.get("parse", {}).get("title", page_name)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            # Drop edit links, navboxes, and the table of contents
            for tag in soup.find_all(["script", "style"]):
                tag.decompose()
            for tag in soup.find_all(class_=["mw-editsection", "toc", "navbox"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            content = "\n".join(lines)
            if len(content) < 100:
                continue

            self.pages.append(
                ScrapedPage(
                    url=f"{wiki_root}/{page_name}",
                    title=f"{title} - openSUSE Wiki",
                    content=content,
                    section=title,
                )
            )
            logger.debug("Fetched wiki page: %s (%d chars)", title, len(content))
            time.sleep(0.3)  # be polite

        logger.info(
            "Fetched %d wiki pages from '%s'", len(self.pages), self.source.name
        )
        self._save_pages()
        return self.pages

    def _save_pages(self) -> None:
        """Persist fetched pages as plain text files for transparency."""
        for page in self.pages:
            safe_name = page.url.rsplit("/", 1)[-1].replace(":", "_")
            filepath = self.output_dir / f"{safe_name}.txt"
            filepath.write_text(
                f"URL: {page.url}\nTitle: {page.title}\nSection: {page.section}\n\n"
                f"{page.content}",
                encoding="utf-8",
            )


def scrape_all_sources(
    sources: list[DocumentationSource], base_dir: Path
) -> list[ScrapedPage]:
    """Scrape all configured documentation sources."""
    all_pages: list[ScrapedPage] = []
    for source in sources:
        output_dir = base_dir / "raw_docs" / source.name.lower().replace(" ", "_")
        if source.kind == "mediawiki":
            scraper: DocumentationScraper | MediaWikiScraper = MediaWikiScraper(
                source, output_dir
            )
        else:
            scraper = DocumentationScraper(source, output_dir)
        pages = scraper.scrape()
        all_pages.extend(pages)
    logger.info("Total scraped pages: %d", len(all_pages))
    return all_pages
