import requests
from bs4 import BeautifulSoup
import os
import time
from config.settings import settings

class SECFilingsScraper:
    def __init__(self, cache_dir: str = settings.SEC_FILINGS_CACHE_PATH):
        self.base_url = "https://www.sec.gov"
        self.search_url = "https://www.sec.gov/cgi-bin/browse-edgar"
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def search_filings(self, ticker: str, doc_type: str = "10-K", count: int = 1) -> list:
        """Searches for recent filings of a given type for a ticker."""
        params = {
            "action": "getcompany",
            "CIK": ticker,
            "type": doc_type,
            "count": count
        }
        response = requests.get(self.search_url, params=params)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        filing_links = []
        for a_tag in soup.find_all('a', id='documentsbutton'):
            link = self.base_url + a_tag['href']
            filing_links.append(link)
        return filing_links

    def get_filing_document_link(self, filing_page_url: str) -> str | None:
        """From a filing summary page, find the link to the actual HTML document."""
        response = requests.get(filing_page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        # Look for the link to the HTML document, typically ending with .htm or .html
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if "Financial_Report" in href and (href.endswith(".htm") or href.endswith(".html")):
                return self.base_url + href
        return None

    def download_and_extract_text(self, url: str, ticker: str, doc_type: str) -> str:
        """Downloads an HTML filing and extracts its text content."""
        filename = os.path.join(self.cache_dir, f"{ticker}_{doc_type}_{os.path.basename(url)}.html")
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                html_content = f.read()
        else:
            response = requests.get(url)
            response.raise_for_status()
            html_content = response.text
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            time.sleep(1) # Be polite to SEC servers

        soup = BeautifulSoup(html_content, 'html.parser')
        # Remove script and style tags
        for script_or_style in soup(['script', 'style']):
            script_or_style.extract()
        text = soup.get_text(separator=' ', strip=True)
        return text

    def get_recent_earnings_report_text(self, ticker: str) -> str | None:
        """A higher-level function to get the text of the most recent 10-Q or 10-K."""
        filing_page_links = self.search_filings(ticker, doc_type="10-Q", count=1)
        if not filing_page_links:
            filing_page_links = self.search_filings(ticker, doc_type="10-K", count=1)

        if filing_page_links:
            filing_page_url = filing_page_links[0]
            doc_link = self.get_filing_document_link(filing_page_url)
            if doc_link:
                return self.download_and_extract_text(doc_link, ticker, "earnings_report")
        return None

# Example Usage:
if __name__ == "__main__":
    scraper = SECFilingsScraper()
    # For Apple (AAPL), try to get the most recent 10-Q or 10-K
    # print(scraper.get_recent_earnings_report_text("AAPL")[:1000]) # Print first 1000 chars