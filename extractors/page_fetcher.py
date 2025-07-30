import requests
from bs4 import BeautifulSoup
import time
import random
from urllib.parse import urlparse


class PageFetcher:
    """
    Handles URL management and HTML fetching for web pages.
    Includes rate limiting protection and retry logic.
    """
    
    def __init__(self, urls=None, delay_range=(1, 3), max_retries=3):
        """
        Initialize the PageFetcher with optional URLs.
        
        Args:
            urls (list, optional): List of URLs to fetch
            delay_range (tuple): Min and max seconds to wait between requests (min, max)
            max_retries (int): Maximum number of retry attempts for failed requests
        """
        self.pages = {}
        self.delay_range = delay_range
        self.max_retries = max_retries
        self.last_request_time = {}  # Track last request time per domain
        
        # Headers to appear more like a real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
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
    
    def _get_domain(self, url):
        """Extract domain from URL for rate limiting per domain."""
        return urlparse(url).netloc
    
    def _apply_rate_limit(self, url):
        """Apply rate limiting based on domain."""
        domain = self._get_domain(url)
        
        if domain in self.last_request_time:
            elapsed = time.time() - self.last_request_time[domain]
            min_delay = self.delay_range[0]
            
            if elapsed < min_delay:
                sleep_time = min_delay - elapsed
                print(f"Rate limiting: waiting {sleep_time:.2f}s before request to {domain}")
                time.sleep(sleep_time)
        
        # Add random delay to appear more human-like
        random_delay = random.uniform(self.delay_range[0], self.delay_range[1])
        time.sleep(random_delay)
        
        # Update last request time
        self.last_request_time[domain] = time.time()
    
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
        Fetch HTML content for a single URL with retry logic and rate limiting.
        
        Args:
            url: URL to fetch
        """
        for attempt in range(self.max_retries):
            try:
                # Apply rate limiting before request
                if attempt == 0:  # Only apply standard rate limit on first attempt
                    self._apply_rate_limit(url)
                
                # Make request with timeout
                response = self.session.get(url, timeout=30)
                
                if response.status_code == 200:
                    self.pages[url] = response.text
                    print(f"HTML fetched for URL: {url}")
                    return
                
                elif response.status_code == 429:
                    # Handle rate limit error
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        wait_time = int(retry_after)
                    else:
                        # Exponential backoff: 5, 10, 20 seconds
                        wait_time = 5 * (2 ** attempt)
                    
                    print(f"Rate limited (429). Waiting {wait_time}s before retry {attempt + 1}/{self.max_retries}")
                    time.sleep(wait_time)
                    
                elif response.status_code in [503, 502, 504]:  # Server errors
                    wait_time = 2 * (2 ** attempt)  # 2, 4, 8 seconds
                    print(f"Server error ({response.status_code}). Waiting {wait_time}s before retry {attempt + 1}/{self.max_retries}")
                    time.sleep(wait_time)
                    
                else:
                    print(f"Failed to fetch URL (status {response.status_code}): {url}")
                    self.pages[url] = None
                    return
                    
            except requests.exceptions.Timeout:
                print(f"Timeout error for {url}. Attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                    
            except requests.exceptions.ConnectionError as e:
                print(f"Connection error for {url}: {e}. Attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    time.sleep(3 * (attempt + 1))
                    
            except Exception as e:
                print(f"Unexpected error fetching {url}: {e}")
                self.pages[url] = None
                return
        
        # If all retries failed
        print(f"Failed to fetch {url} after {self.max_retries} attempts")
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
    
    def close(self):
        """Close the session when done."""
        self.session.close()