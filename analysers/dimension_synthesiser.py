from typing import List, Dict
from models.data_models import KeywordData, DimensionHierarchy
from llm.deepseek_client import DeepSeekClient
import re


class DimensionSynthesiser:
    """Synthesize dimensions from multiple keywords into unified hierarchy"""
    
    def __init__(self, llm_client: DeepSeekClient):
        self.llm = llm_client
    
    def synthesize(self, key_word: str, keywords_data: List[KeywordData]) -> DimensionHierarchy:
        """
        Synthesize dimensions from multiple keywords into a hierarchy
        """
        # Build the prompt
        messages = self._build_synthesis_prompt(key_word, keywords_data)
        
        # Get hierarchical text from LLM
        print(f"Synthesizing dimensions for '{key_word}' from {len(keywords_data)} keywords...")
        
        try:
            print("Calling LLM...")
            full_response = self.llm.complete(messages, temperature=0.3)
            
            # Extract just the hierarchy part
            hierarchy_text = self._extract_hierarchy_from_response(full_response, key_word)
            
            print(f"Extracted hierarchy ({len(hierarchy_text)} chars):")
            print(hierarchy_text)
            
        except Exception as e:
            print(f"ERROR calling LLM: {str(e)}")
            hierarchy_text = self._create_fallback_hierarchy(key_word, keywords_data)
        
        # Create and parse the hierarchy
        dimension_hierarchy = DimensionHierarchy(
            key_word=key_word,
            hierarchy_text=hierarchy_text
        )
        dimension_hierarchy.parse_hierarchy()
        
        return dimension_hierarchy
    
    def _extract_hierarchy_from_response(self, response: str, key_word: str) -> str:
        """Extract just the hierarchy structure from LLM response"""
        if not response:
            return ""
        
        # Look for the hierarchy structure
        lines = response.strip().split('\n')
        hierarchy_lines = []
        in_hierarchy = False
        
        for line in lines:
            # Start capturing when we see the key word at the beginning
            if line.strip() == key_word or (not in_hierarchy and key_word.lower() in line.lower() and line.strip().startswith(key_word)):
                in_hierarchy = True
                hierarchy_lines.append(key_word)  # Ensure clean root
                continue
            
            # Stop capturing when we hit explanatory text
            if in_hierarchy:
                # Check if this looks like hierarchy (starts with spaces or -)
                if line.strip() and (line.startswith(' ') or line.startswith('-')):
                    # Clean the line
                    clean_line = line.rstrip()
                    if clean_line.strip().startswith('-'):
                        hierarchy_lines.append(clean_line)
                elif line.strip() == '':
                    # Empty line might be end of hierarchy
                    continue
                else:
                    # Non-indented, non-empty line = end of hierarchy
                    break
        
        return '\n'.join(hierarchy_lines)
    
    def _build_synthesis_prompt(self, key_word: str, keywords_data: List[KeywordData]) -> List[Dict]:
        """Build the prompt for dimension synthesis"""
        
        system_prompt = f"""You must create ONLY a hierarchical structure with '{key_word}' as the root.

FORMAT RULES:
1. Start with '{key_word}' on the first line
2. Use EXACTLY 2 spaces per indentation level
3. Use "- " before each item (except the root)
4. Maximum 3 levels deep
5. Return ONLY the hierarchy - no explanations, no markdown, no extra text

CORRECT EXAMPLE:
{key_word}
  - category one
    -- subcategory one
    -- subcategory two
  - category two
    -- subcategory three

DO NOT add any text before or after the hierarchy."""

        # Build user prompt
        user_prompt_parts = [f"Create a hierarchy for '{key_word}' from these dimensions:\n"]
        
        for kw_data in keywords_data:
            user_prompt_parts.append(f"\nFrom '{kw_data.keyword}':")
            
            if isinstance(kw_data.raw_dimensions, dict):
                for main_dim, sub_dims in list(kw_data.raw_dimensions.items())[:5]:
                    user_prompt_parts.append(f"• {main_dim}")
                    for sub_dim in sub_dims[:3]:
                        user_prompt_parts.append(f"  - {sub_dim}")
            else:
                for dim in kw_data.raw_dimensions[:8]:
                    user_prompt_parts.append(f"• {dim}")
        
        user_prompt_parts.append(f"\nOrganize these into a single hierarchy under '{key_word}'. Return ONLY the hierarchy structure, nothing else.")
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n".join(user_prompt_parts)}
        ]
    
    def _create_fallback_hierarchy(self, key_word: str, keywords_data: List[KeywordData]) -> str:
        """Create a simple fallback hierarchy if LLM fails"""
        lines = [key_word]
        
        for kw_data in keywords_data:
            lines.append(f"  - {kw_data.keyword}")
            
            if isinstance(kw_data.raw_dimensions, dict):
                for main_dim in list(kw_data.raw_dimensions.keys())[:3]:
                    lines.append(f"    -- {main_dim}")
            else:
                for dim in kw_data.raw_dimensions[:3]:
                    lines.append(f"    -- {dim}")
        
        return "\n".join(lines)
    
    def visualize_hierarchy(self, hierarchy: DimensionHierarchy) -> str:
        """Create a visual representation of the hierarchy"""
        if not hierarchy.structured:
            hierarchy.parse_hierarchy()
        
        lines = [f"🌳 {hierarchy.key_word}"]
        
        for item in hierarchy.structured:
            level = item['level']
            name = item['name']
            
            if level == 0:
                continue  # Skip root
            
            # Create indentation
            if level == 1:
                lines.append(f"├── {name}")
            elif level == 2:
                lines.append(f"│   └── {name}")
            else:
                lines.append(f"│       └── {name}")
        
        return "\n".join(lines)