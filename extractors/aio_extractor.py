from bs4 import BeautifulSoup
from typing import List, Dict
import re
import json


class AIOExtractor:
    """Extract dimensions (headings) from AIO HTML content with hierarchy preserved"""
    
    def extract_dimensions(self, aio_html: str) -> Dict[str, List[str]]:
        """
        Extract dimensions from AIO HTML preserving hierarchy
        """
        if not aio_html or not aio_html.strip():
            return {}
        
        # Handle escaped HTML (when stored as string literal)
        if '\\"' in aio_html:
            # Remove surrounding quotes if present
            aio_html = aio_html.strip().strip('"').strip("'")
            # Unescape the quotes
            aio_html = aio_html.replace('\\"', '"')
            # Unescape newlines if present
            aio_html = aio_html.replace('\\n', '\n')
        
        soup = BeautifulSoup(aio_html, 'html.parser')
        
        # Debug: Check if parsing worked
        test_divs = soup.find_all('div', class_='WaaZC')
        print(f"Debug: Found {len(test_divs)} WaaZC divs")
        
        hierarchy = {}
        current_main_dimension = None
        
        # Process all content blocks
        content_blocks = soup.find_all('div', class_='WaaZC')
        
        for block in content_blocks:
            # Check if this block contains a main heading (pyPiTc class)
            main_heading = block.find('div', class_='pyPiTc')
            if main_heading:
                text = self._clean_text(main_heading.get_text())
                if text:
                    current_main_dimension = text
                    hierarchy[current_main_dimension] = []
            
            # Look for sub-dimensions in the same block or following blocks
            list_container = block.find('ul')
            if list_container and current_main_dimension:
                list_items = list_container.find_all('li', class_='K3KsMc')
                for item in list_items:
                    strong_tag = item.find('strong')
                    if strong_tag:
                        sub_dim = self._clean_text(strong_tag.get_text())
                        if sub_dim:
                            hierarchy[current_main_dimension].append(sub_dim)
        
        return hierarchy
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove trailing colons
        text = text.rstrip(':')
        
        return text.strip()