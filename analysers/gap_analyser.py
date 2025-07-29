from typing import Dict, List, Tuple
from models.data_models import DimensionHierarchy, ExtractedContent, DimensionScore, GapAnalysisResult
from llm.deepseek_client import DeepSeekClient
import json
from datetime import datetime
import uuid


class GapAnalyser:
    """Analyze content gaps against dimension hierarchy"""
    
    def __init__(self, llm_client: DeepSeekClient):
        self.llm = llm_client
    
    def analyze(
        self, 
        content: ExtractedContent, 
        hierarchy: DimensionHierarchy,
        key_word: str
    ) -> GapAnalysisResult:
        """
        Analyze how well content covers the dimension hierarchy
        
        Args:
            content: Extracted content from target page
            hierarchy: Synthesized dimension hierarchy
            key_word: Central keyword for context
            
        Returns:
            GapAnalysisResult with scores and recommendations
        """
        print(f"Analyzing content gaps for '{key_word}'...")
        
        # Get all dimensions to analyze
        dimensions_to_analyze = self._get_dimensions_to_analyze(hierarchy)
        
        # Analyze each dimension
        dimension_scores = []
        for dim_path, dim_info in dimensions_to_analyze:
            print("Analysing a new dimension")
            score = self._analyze_dimension_coverage(
                content, 
                dim_path, 
                dim_info,
                hierarchy
            )
            dimension_scores.append(score)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(dimension_scores)
        
        # Generate insights
        strengths, weaknesses = self._identify_strengths_weaknesses(dimension_scores)
        recommendations = self._generate_recommendations(dimension_scores, hierarchy)
        
        return GapAnalysisResult(
            analysis_id=str(uuid.uuid4()),
            created_at=datetime.now(),
            key_word=key_word,
            target_url=content.url,
            dimension_scores=dimension_scores,
            overall_score=overall_score,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations
        )
    
    def _get_dimensions_to_analyze(self, hierarchy: DimensionHierarchy) -> List[Tuple[str, Dict]]:
        """Get list of dimension paths to analyze - only up to level 2"""
        dimensions = []
        
        if not hierarchy.structured:
            hierarchy.parse_hierarchy()
        
        # Build a map of parent -> children for easy lookup
        parent_children_map = {}
        for item in hierarchy.structured:
            if item['level'] > 0:  # Skip root
                path_parts = item['path'].split(' > ')
                if len(path_parts) > 1:
                    parent_path = ' > '.join(path_parts[:-1])
                    if parent_path not in parent_children_map:
                        parent_children_map[parent_path] = []
                    parent_children_map[parent_path].append(item)
        
        # Only analyze dimensions up to level 2
        for item in hierarchy.structured:
            if 0 < item['level'] <= 2:  # Skip root (0) and level 3+
                # Add children info to the dimension
                children = parent_children_map.get(item['path'], [])
                item['children'] = children
                dimensions.append((item['path'], item))
        
        return dimensions
    
    def _analyze_dimension_coverage(
        self, 
        content: ExtractedContent,
        dim_path: str,
        dim_info: Dict,
        hierarchy: DimensionHierarchy
    ) -> DimensionScore:
        """Analyze how well content covers a specific dimension"""
        
        # Build prompt for LLM
        messages = self._build_analysis_prompt(content, dim_path, dim_info, hierarchy)
        
        # Get analysis from LLM
        try:
            response = self.llm.complete_json(messages, temperature=0.3)
            
            # Extract score and reasoning
            score = response.get('score', 0)
            reasoning = response.get('reasoning', 'No reasoning provided')
            child_coverage = response.get('child_coverage', None)
            
            # Validate score
            if score not in [0, 25, 50, 75, 100]:
                print(f"Warning: Invalid score {score} for {dim_path}, defaulting to 0")
                score = 0
            
            return DimensionScore(
                dimension_path=dim_path,
                score=score,
                reasoning=reasoning,
                child_coverage=child_coverage
            )
            
        except Exception as e:
            print(f"Error analyzing {dim_path}: {str(e)}")
            return DimensionScore(
                dimension_path=dim_path,
                score=0,
                reasoning=f"Analysis failed: {str(e)}"
            )
    
    def _build_analysis_prompt(
        self,
        content: ExtractedContent,
        dim_path: str,
        dim_info: Dict,
        hierarchy: DimensionHierarchy
    ) -> List[Dict]:
        """Build prompt for dimension analysis"""
        
        system_prompt = """You are analyzing how well a webpage covers a specific topic/dimension.

    SCORING CRITERIA:
    - 100 = Excellent: Comprehensive coverage, all or most sub-topics covered with detail
    - 75 = Good: Clear coverage with good detail, most sub-topics mentioned
    - 50 = Average: Basic coverage, about half of sub-topics covered
    - 25 = Poor: Minimal mention, few sub-topics covered
    - 0 = Missing: No evidence of this topic

    When a dimension has sub-topics (children), base your score primarily on how many and how well those sub-topics are covered in the content.

    Return JSON with this structure:
    {
        "score": <0|25|50|75|100>,
        "reasoning": "<brief explanation>",
        "child_coverage": "<X/Y subtopics covered>" // only if dimension has children
    }"""

        # Get content summary
        content_text = content.get_all_text()[:3000]  # Limit for prompt
        
        # Get children from dim_info
        children = dim_info.get('children', [])
        children_names = [child['name'] for child in children]
        
        user_prompt = f"""Analyze how well this content covers the dimension: "{dim_path}"

    CONTENT FROM PAGE:
    Title: {content.title}
    Meta: {content.meta_description}

    Main Content Sample:
    {content_text}

    DIMENSION TO ANALYZE: {dim_path}
    {f"SUB-TOPICS TO CHECK FOR: {', '.join(children_names)}" if children_names else "This is a leaf dimension with no sub-topics."}

    {"For scoring, check how many and how well the sub-topics are covered in the content." if children_names else "Score based on how well this specific topic is covered."}

    Score the coverage and provide reasoning."""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def _calculate_overall_score(self, dimension_scores: List[DimensionScore]) -> float:
        """Calculate weighted overall score"""
        if not dimension_scores:
            return 0.0
        
        # Simple average for now - could add weighting later
        total_score = sum(ds.score for ds in dimension_scores)
        return round(total_score / len(dimension_scores), 1)
    
    def _identify_strengths_weaknesses(
        self, 
        dimension_scores: List[DimensionScore]
    ) -> Tuple[List[str], List[str]]:
        """Identify content strengths and weaknesses"""
        strengths = []
        weaknesses = []
        
        for ds in dimension_scores:
            if ds.score >= 75:
                strengths.append(f"Strong coverage of {ds.dimension_path.split(' > ')[-1]}")
            elif ds.score <= 25:
                weaknesses.append(f"Weak/missing coverage of {ds.dimension_path.split(' > ')[-1]}")
        
        # If no specific strengths/weaknesses, add general ones
        if not strengths:
            if any(ds.score >= 50 for ds in dimension_scores):
                strengths.append("Some topics covered at a basic level")
        
        if not weaknesses:
            if any(ds.score < 50 for ds in dimension_scores):
                weaknesses.append("Several topics need more depth")
        
        return strengths, weaknesses
    
    def _generate_recommendations(
        self,
        dimension_scores: List[DimensionScore],
        hierarchy: DimensionHierarchy
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Group by score level
        missing = [ds for ds in dimension_scores if ds.score == 0]
        poor = [ds for ds in dimension_scores if ds.score == 25]
        average = [ds for ds in dimension_scores if ds.score == 50]
        
        # Priority 1: Add missing content
        if missing:
            topics = [ds.dimension_path.split(' > ')[-1] for ds in missing[:3]]
            recommendations.append(f"Add sections covering: {', '.join(topics)}")
        
        # Priority 2: Improve poor coverage
        if poor:
            topics = [ds.dimension_path.split(' > ')[-1] for ds in poor[:3]]
            recommendations.append(f"Expand content on: {', '.join(topics)}")
        
        # Priority 3: Enhance average coverage
        if average and len(recommendations) < 3:
            topics = [ds.dimension_path.split(' > ')[-1] for ds in average[:2]]
            recommendations.append(f"Add more detail to: {', '.join(topics)}")
        
        # Add a general recommendation if needed
        if not recommendations:
            recommendations.append("Content covers most topics well - consider adding more examples and case studies")
        
        return recommendations[:5]  # Limit to 5 recommendations