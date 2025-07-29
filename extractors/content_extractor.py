from typing import Dict, Optional
from .page_fetcher import PageFetcher
from .hierarchical_scraper import HierarchicalScraper
from models.data_models import ExtractedContent


class ContentExtractor:
    """Orchestrates URL fetching and content extraction"""
    
    def __init__(self):
        self.fetcher = PageFetcher()
        self.scraper = HierarchicalScraper()
    
    def extract_from_url(self, url: str) -> ExtractedContent:
        """
        Extract structured content from a URL
        
        Args:
            url: Target URL to analyze
            
        Returns:
            ExtractedContent object with structured page data
            
        Raises:
            ValueError: If URL fetch fails or content is empty
        """
        # Add URL and fetch
        self.fetcher.add_pages(url)
        self.fetcher.fetch_url(url)
        
        # Get BeautifulSoup object
        soup = self.fetcher.get_soup(url)
        if not soup:
            raise ValueError(f"Failed to fetch content from {url}")
        
        # Extract structure using hierarchical scraper
        structure = self.scraper.extract_structure(soup, url)
        
        # Convert to our data model
        return self._convert_to_extracted_content(url, structure)
    
    def _convert_to_extracted_content(self, url: str, structure: Dict) -> ExtractedContent:
        """
        Convert scraper output to ExtractedContent model
        
        Args:
            url: The URL that was scraped
            structure: Output from HierarchicalScraper
            
        Returns:
            ExtractedContent object
        """
        # Handle missing fields gracefully
        title = structure.get('title', '')
        meta_description = structure.get('meta_description', '')
        content_blocks = structure.get('content', [])
        
        # Validate we have some content
        if not title and not content_blocks:
            raise ValueError(f"No meaningful content extracted from {url}")
        
        return ExtractedContent(
            url=url,
            title=title,
            meta_description=meta_description,
            content_blocks=content_blocks
        )
    
    def extract_from_html(self, html: str, url: str = "unknown") -> ExtractedContent:
        """
        Extract structured content from HTML string (bypass fetching)
        
        Args:
            html: HTML content as string
            url: URL for reference (optional)
            
        Returns:
            ExtractedContent object
        """
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'html.parser')
        structure = self.scraper.extract_structure(soup, url)
        
        return self._convert_to_extracted_content(url, structure)