import requests
from bs4 import BeautifulSoup


class PageFetcher:
    """
    Handles URL management and HTML fetching for web pages.
    Separates the concern of retrieving content from parsing/analyzing it.
    """
    
    def __init__(self, urls=None):
        """
        Initialize the PageFetcher with optional URLs.
        
        Args:
            urls (list, optional): List of URLs to fetch
        """
        self.pages = {}
        if urls:
            self.add_pages(urls)
    
    def add_pages(self, urls):
        """
        Add new URLs to the pages dictionary.
        
        Args:
            urls: Can be a single URL string or a list of URLs
        """
        if isinstance(urls, list):
            for url in urls:
                self._add_single_page(url)
        else:
            self._add_single_page(urls)
    
    def _add_single_page(self, url):
        """
        Add a single URL to the pages dictionary.
        
        Args:
            url: URL string to add
        """
        if url not in self.pages:
            self.pages[url] = None
            print(f"URL added: {url}")
        else:
            print(f"URL already exists: {url}")
    
    def fetch_all(self):
        """
        Fetch HTML content for all URLs that haven't been fetched yet.
        """
        for url in self.pages:
            if self.pages[url] is None:
                self._fetch_html(url)
    
    def fetch_url(self, url):
        """
        Fetch HTML content for a specific URL.
        
        Args:
            url: URL to fetch
        """
        if url in self.pages:
            self._fetch_html(url)
        else:
            print(f"URL not in pages list: {url}")
    
    def _fetch_html(self, url):
        """
        Fetch HTML content for a single URL and store it.
        
        Args:
            url: URL to fetch
        """
        try:
            response = requests.get(url)
            if response.status_code == 200 or response.status_code == 202:
                self.pages[url] = response.text
                print(f"HTML fetched for URL: {url}")
            else:
                print(f"Failed to fetch URL (status {response.status_code}): {url}")
                self.pages[url] = None
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            self.pages[url] = None
    
    def get_html(self, url):
        """
        Get the raw HTML content for a specific URL.
        
        Args:
            url: URL to get HTML for
            
        Returns:
            str: HTML content or None if not available
        """
        if url in self.pages:
            return self.pages[url]
        else:
            print(f"URL not found: {url}")
            return None
    
    def get_soup(self, url):
        """
        Get a BeautifulSoup object for a specific URL.
        
        Args:
            url: URL to parse
            
        Returns:
            BeautifulSoup: Parsed HTML or None if not available
        """
        html_content = self.get_html(url)
        if html_content:
            return BeautifulSoup(html_content, 'html.parser')
        else:
            return None
    
    def get_all_urls(self):
        """
        Get a list of all URLs managed by this fetcher.
        
        Returns:
            list: All URLs
        """
        return list(self.pages.keys())
    
    def get_fetched_urls(self):
        """
        Get a list of URLs that have been successfully fetched.
        
        Returns:
            list: URLs with HTML content
        """
        return [url for url, html in self.pages.items() if html is not None]
    
    def clear_html(self, url):
        """
        Clear the stored HTML for a specific URL.
        
        Args:
            url: URL to clear
        """
        if url in self.pages:
            self.pages[url] = None
            print(f"HTML cleared for URL: {url}")
    
    def remove_url(self, url):
        """
        Remove a URL completely from the pages dictionary.
        
        Args:
            url: URL to remove
        """
        if url in self.pages:
            del self.pages[url]
            print(f"URL removed: {url}")
        else:
            print(f"URL not found: {url}")