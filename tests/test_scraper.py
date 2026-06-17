"""Tests for the documentation scraper."""

from unittest.mock import MagicMock

from opensuse_ai.config import DocumentationSource
from opensuse_ai.scraper import DocumentationScraper, ScrapedPage


def test_scraped_page_dataclass():
    """ScrapedPage should store all fields."""
    page = ScrapedPage(
        url="https://example.com/docs/page1",
        title="Test Page",
        content="This is test content for the page.",
        section="Getting Started",
    )
    assert page.url == "https://example.com/docs/page1"
    assert page.title == "Test Page"
    assert page.section == "Getting Started"
    assert len(page.content) > 10


def test_extract_content():
    """Content extraction should handle typical openSUSE doc HTML."""
    from bs4 import BeautifulSoup

    html = """
    <html>
    <head><title>Installing Packages - openSUSE Leap</title></head>
    <body>
    <nav>Navigation links</nav>
    <div id="content">
        <h1>Installing Packages</h1>
        <p>Use zypper to install packages on openSUSE.</p>
        <p>Example: zypper install vim</p>
        <p>You can also search for packages using zypper search.</p>
    </div>
    <footer>Footer content</footer>
    </body>
    </html>
    """
    source = DocumentationSource(
        name="test", base_url="https://example.com", start_urls=[], max_pages=10
    )
    scraper = DocumentationScraper(source, output_dir=MagicMock())
    soup = BeautifulSoup(html, "html.parser")

    page = scraper._extract_content("https://example.com/docs/install", soup)

    assert page is not None
    assert "zypper" in page.content
    assert "Installing Packages" in page.section
    # Navigation and footer should be removed
    assert "Navigation links" not in page.content
    assert "Footer content" not in page.content
