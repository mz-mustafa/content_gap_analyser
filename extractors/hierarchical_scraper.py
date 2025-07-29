from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import urlparse, urljoin
import json


class HierarchicalScraper:
    """
    Extracts hierarchical structure from HTML pages, maintaining order
    and relationships between headings and their content.
    """
    
    def __init__(self, base_url=None):
        """
        Initialize the scraper.
        
        Args:
            base_url (str, optional): Base URL for determining internal links
        """
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc if base_url else None
    
    def extract_structure(self, soup, base_url=None):
        """
        Extract the hierarchical structure from a BeautifulSoup object.
        
        Args:
            soup: BeautifulSoup object
            base_url: URL of the page (for internal link detection)
            
        Returns:
            dict: Hierarchical structure with title, meta_description, and content
        """
        if base_url:
            self.base_url = base_url
            self.base_domain = urlparse(base_url).netloc
        
        structure = {
            'title': self._get_title(soup),
            'meta_description': self._get_meta_description(soup)
        }
        
        # First, capture navigation/menu links
        nav_elements = self._get_nav_elements(soup)
        nav_block = self._extract_navigation_from_elements(nav_elements)
        
        # Then traverse the main content, excluding nav elements
        content_blocks = []
        if nav_block:
            content_blocks.append(nav_block)
        
        main_content = self._traverse_dom_sequentially(soup, nav_elements)
        content_blocks.extend(main_content)
        
        structure['content'] = content_blocks
        
        return structure
    
    def _get_nav_elements(self, soup):
        """Get navigation elements to process and exclude from main content."""
        nav_elements = soup.find_all('nav')
        header = soup.find('header')
        if header:
            nav_elements.append(header)
        return nav_elements
    
    def _extract_navigation_from_elements(self, nav_elements):
        """Extract navigation content from given elements."""
        if not nav_elements:
            return None
            
        navigation_links = []
        navigation_buttons = []
        
        for nav_element in nav_elements:
            # Extract links
            links = nav_element.find_all('a')
            for link in links:
                href = link.get('href', '')
                if href and self._is_internal_link(href):
                    link_text = link.get_text().strip()
                    if link_text and len(link_text) < 50 and link_text not in navigation_links:
                        navigation_links.append(link_text)
            
            # Extract buttons
            buttons = nav_element.find_all(['button'], limit=10)
            for button in buttons:
                button_text = button.get_text().strip()
                if button_text and len(button_text) < 50 and button_text not in navigation_buttons:
                    navigation_buttons.append(button_text)
        
        # Only create navigation block if we found items
        if navigation_links or navigation_buttons:
            nav_block = {
                'level': 'navigation',
                'heading': 'Main Navigation'
            }
            if navigation_links:
                nav_block['links'] = navigation_links
            if navigation_buttons:
                nav_block['buttons'] = navigation_buttons
            return nav_block
        
        return None
    
    def _get_title(self, soup):
        """Extract page title."""
        title_tag = soup.find('title')
        return title_tag.get_text().strip() if title_tag else None
    
    def _get_meta_description(self, soup):
        """Extract meta description."""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if not meta_desc:
            meta_desc = soup.find('meta', attrs={'property': 'og:description'})
        return meta_desc.get('content', '').strip() if meta_desc else None

    
    def _is_footer_content(self, element):
        """
        Detect if an element is part of footer content.
        
        Returns:
            bool: True if element is in footer
        """
        # Check if element is within a footer tag
        footer_parent = element.find_parent('footer')
        if footer_parent:
            return True
        
        # Check for footer-related classes in immediate parent only
        parent = element.parent
        if parent and parent.get('class'):
            classes = ' '.join(parent.get('class')).lower()
            if 'footer' in classes:
                return True
        
        return False
    
    def _traverse_dom_sequentially(self, soup, nav_elements=None):
        """
        Traverse the DOM sequentially, maintaining order and hierarchy.
        
        Args:
            soup: BeautifulSoup object
            nav_elements: List of navigation elements to skip
            
        Returns:
            list: Content blocks with headings and their associated content
        """
        content_blocks = []
        current_block = None
        current_level = None
        
        # Get the body or use the whole soup if no body
        body = soup.body if soup.body else soup
        
        # Find all relevant elements in order
        relevant_tags = ['h1', 'h2', 'h3', 'p', 'a', 'button', 'input']
        all_elements = body.find_all(relevant_tags)
        
        for element in all_elements:
            # Skip if element is within navigation elements
            if nav_elements:
                skip = False
                for nav in nav_elements:
                    if nav and element in nav.descendants:
                        skip = True
                        break
                if skip:
                    continue
            
            # Skip footer content
            if self._is_footer_content(element):
                continue
            
            if element.name in ['h1', 'h2', 'h3']:
                # Save previous block if exists
                if current_block:
                    content_blocks.append(self._clean_block(current_block))
                
                # Start new block
                current_level = element.name
                current_block = {
                    'level': current_level,
                    'heading': element.get_text().strip(),
                    'links': [],
                    'buttons': [],
                    'paragraphs': []
                }
            
            elif current_block:  # Only process if we have a current heading context
                if element.name == 'p' and current_level == 'h1':
                    # Only collect paragraphs under h1
                    text = element.get_text().strip()
                    if text:
                        current_block['paragraphs'].append(text)
                
                elif element.name == 'a':
                    # Check if it's an internal link
                    href = element.get('href', '')
                    if href and self._is_internal_link(href):
                        link_text = element.get_text().strip()
                        if link_text and link_text not in current_block['links']:
                            current_block['links'].append(link_text)
                
                elif element.name == 'button':
                    button_text = element.get_text().strip()
                    if button_text and button_text not in current_block['buttons']:
                        current_block['buttons'].append(button_text)
                
                elif element.name == 'input' and element.get('type') in ['button', 'submit']:
                    button_text = element.get('value', '').strip()
                    if button_text and button_text not in current_block['buttons']:
                        current_block['buttons'].append(button_text)
        
        # Don't forget the last block
        if current_block:
            content_blocks.append(self._clean_block(current_block))
        
        # Also check for link-styled buttons within each block's section
        self._find_link_buttons(body, content_blocks)
        
        return content_blocks
    
    def _clean_block(self, block):
        """
        Clean a content block by removing empty arrays and unnecessary fields.
        
        Args:
            block: Content block dictionary
            
        Returns:
            dict: Cleaned block
        """
        cleaned = {
            'level': block['level'],
            'heading': block['heading']
        }
        
        # Only add non-empty arrays
        if block['links']:
            cleaned['links'] = block['links']
        if block['buttons']:
            cleaned['buttons'] = block['buttons']
        
        # Only add paragraphs for h1
        if block['level'] == 'h1' and block['paragraphs']:
            cleaned['paragraphs'] = block['paragraphs']
        
        return cleaned
    
    def _is_internal_link(self, href):
        """
        Determine if a link is internal.
        
        Args:
            href: Link URL
            
        Returns:
            bool: True if internal, False otherwise
        """
        if not href:
            return False
        
        # Anchor links are internal
        if href.startswith('#'):
            return True
        
        # Relative links are internal
        if href.startswith('/'):
            return True
        
        # Parse the URL
        parsed = urlparse(href)
        
        # No scheme means relative link
        if not parsed.scheme:
            return True
        
        # If we have a base domain, check if it matches
        if self.base_domain and parsed.netloc:
            return parsed.netloc == self.base_domain
        
        # mailto, tel, etc. are not internal
        if parsed.scheme in ['mailto', 'tel', 'javascript']:
            return False
        
        return False
    
    def _find_link_buttons(self, soup, content_blocks):
        """
        Find links that are styled as buttons and add them to the appropriate blocks.
        This is a second pass to catch button-styled links.
        """
        # Find all links with button-like classes
        button_links = soup.find_all('a', class_=lambda x: x and any(
            btn in ' '.join(x).lower() for btn in ['btn', 'button']
        ))
        
        for link in button_links:
            # Skip footer content
            if self._is_footer_content(link):
                continue
                
            # Skip if not internal
            href = link.get('href', '')
            if not self._is_internal_link(href):
                continue
            
            button_text = link.get_text().strip()
            if not button_text:
                continue
            
            # Find which block this button belongs to
            # by finding the nearest preceding heading
            for element in link.find_all_previous(['h1', 'h2', 'h3']):
                heading_text = element.get_text().strip()
                # Find the matching block
                for i, block in enumerate(content_blocks):
                    if block.get('heading') == heading_text:
                        # Check if this button is already in links or buttons
                        existing_links = block.get('links', [])
                        existing_buttons = block.get('buttons', [])
                        
                        if button_text not in existing_links and button_text not in existing_buttons:
                            if 'buttons' not in content_blocks[i]:
                                content_blocks[i]['buttons'] = []
                            content_blocks[i]['buttons'].append(button_text)
                        break
                break
    
    def extract_structure_json(self, soup, base_url=None):
        """
        Extract structure and return as formatted JSON string.
        
        Args:
            soup: BeautifulSoup object
            base_url: URL of the page
            
        Returns:
            str: JSON formatted structure
        """
        structure = self.extract_structure(soup, base_url)
        return json.dumps(structure, indent=2, ensure_ascii=False)