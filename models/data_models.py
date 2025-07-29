from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import json


@dataclass
class KeywordData:
    """Represents a keyword with its AIO HTML content"""
    keyword: str
    aio_html: str
    raw_dimensions: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return {
            'keyword': self.keyword,
            'aio_html': self.aio_html[:100] + '...' if len(self.aio_html) > 100 else self.aio_html,
            'raw_dimensions': self.raw_dimensions
        }


@dataclass
class DimensionHierarchy:
    """Represents the synthesized dimension hierarchy"""
    key_word: str
    hierarchy_text: str  # Raw indented text from LLM
    structured: Dict = field(default_factory=dict)  # Parsed structure
    
    def parse_hierarchy(self):
        """Parse the indented text into structured format"""
        lines = self.hierarchy_text.strip().split('\n')
        result = []
        
        for line in lines:
            if line.strip():
                # Count indentation level
                indent = len(line) - len(line.lstrip())
                level = indent // 2  # Assuming 2 spaces per level
                name = line.strip().lstrip('- ')
                
                result.append({
                    'name': name,
                    'level': level,
                    'path': self._build_path(result, name, level)
                })
        
        self.structured = result
        return result
    
    def _build_path(self, existing, name, level):
        """Build the path string for a dimension"""
        if level == 0:
            return name
        
        # Find parent (last item with level = current_level - 1)
        parent = None
        for item in reversed(existing):
            if item['level'] == level - 1:
                parent = item
                break
        
        if parent:
            return f"{parent['path']} > {name}"
        return name


@dataclass
class DimensionScore:
    """Score for a single dimension"""
    dimension_path: str
    score: int  # 0, 25, 50, 75, 100
    reasoning: str
    child_coverage: Optional[str] = None
    

@dataclass
class GapAnalysisResult:
    """Complete gap analysis results"""
    analysis_id: str
    created_at: datetime
    key_word: str
    target_url: str
    dimension_scores: List[DimensionScore]
    overall_score: float
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    
    def to_json(self):
        """Convert to JSON-serializable dict"""
        return {
            'analysis_id': self.analysis_id,
            'created_at': self.created_at.isoformat(),
            'key_word': self.key_word,
            'target_url': self.target_url,
            'dimension_scores': [
                {
                    'path': ds.dimension_path,
                    'score': ds.score,
                    'reasoning': ds.reasoning,
                    'child_coverage': ds.child_coverage
                }
                for ds in self.dimension_scores
            ],
            'overall_score': self.overall_score,
            'strengths': self.strengths,
            'weaknesses': self.weaknesses,
            'recommendations': self.recommendations
        }


@dataclass
class ExtractedContent:
    """Structured content extracted from a webpage"""
    url: str
    title: str
    meta_description: str
    content_blocks: List[Dict]
    
    def get_all_text(self) -> str:
        """Get all text content for analysis"""
        texts = [self.title, self.meta_description]
        
        for block in self.content_blocks:
            texts.append(block.get('heading', ''))
            texts.extend(block.get('paragraphs', []))
            texts.extend(block.get('links', []))
            
        return ' '.join(filter(None, texts))