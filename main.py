#!/usr/bin/env python3
"""
Content Gap Analyser - Main Workflow
Can run full analysis or use saved intermediate results
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

from config import DEEPSEEK_API_KEY
from models.data_models import KeywordData, DimensionHierarchy, ExtractedContent, GapAnalysisResult
from extractors.aio_extractor import AIOExtractor
from extractors.content_extractor import ContentExtractor
from analysers.dimension_synthesiser import DimensionSynthesizer
from analysers.gap_analyser import GapAnalyser
from llm.deepseek_client import DeepSeekClient


class ContentGapAnalyser:
    """Main workflow orchestrator"""
    
    def __init__(self, api_key: str = None):
        api_key = api_key or DEEPSEEK_API_KEY
        self.llm_client = DeepSeekClient(api_key)
        
        # Initialize components
        self.aio_extractor = AIOExtractor()
        self.content_extractor = ContentExtractor()
        self.synthesizer = DimensionSynthesizer(self.llm_client)
        self.analyzer = GapAnalyser(self.llm_client)
        
        # Ensure output directory exists
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
    
    def run_full_analysis(
        self,
        key_word: str,
        keywords_file: str,
        target_url: str,
        save_intermediate: bool = True
    ) -> dict:
        """
        Run complete content gap analysis workflow
        
        Args:
            key_word: Central concept (e.g., "digital reporting")
            keywords_file: Path to CSV with keywords and AIO HTML
            target_url: URL to analyze
            save_intermediate: Whether to save intermediate results
            
        Returns:
            Complete analysis results
        """
        print(f"\n{'='*60}")
        print(f"Content Gap Analysis")
        print(f"Key Word: {key_word}")
        print(f"Target URL: {target_url}")
        print(f"{'='*60}\n")
        
        # Step 1: Load keywords and extract dimensions
        print("Step 1: Extracting dimensions from keywords...")
        keywords_data = self._load_keywords_from_csv(keywords_file)
        
        if save_intermediate:
            self._save_intermediate("keywords_dimensions.json", {
                "keywords": [
                    {
                        "keyword": kw.keyword,
                        "dimensions": kw.raw_dimensions
                    }
                    for kw in keywords_data
                ]
            })
        
        # Step 2: Synthesize dimension hierarchy
        print("\nStep 2: Synthesizing dimension hierarchy...")
        hierarchy = self.synthesizer.synthesize(key_word, keywords_data)
        
        if save_intermediate:
            self._save_intermediate("dimension_hierarchy.json", {
                "key_word": hierarchy.key_word,
                "hierarchy_text": hierarchy.hierarchy_text,
                "structured": hierarchy.structured
            })
        
        # Step 3: Extract content from target URL
        print("\nStep 3: Extracting content from target URL...")
        content = self.content_extractor.extract_from_url(target_url)
        
        if save_intermediate:
            self._save_intermediate("extracted_content.json", {
                "url": content.url,
                "title": content.title,
                "meta_description": content.meta_description,
                "content_blocks": content.content_blocks
            })
        
        # Step 4: Analyze gaps
        print("\nStep 4: Analyzing content gaps...")
        analysis = self.analyzer.analyze(content, hierarchy, key_word)
        
        # Save final results
        results = analysis.to_json()
        self._save_results(results)
        
        # Display summary
        self._display_summary(analysis)
        
        return results
    
    def run_gap_analysis_only(
        self,
        hierarchy_file: str,
        content_file: str,
        key_word: str = None
    ) -> dict:
        """
        Run only gap analysis using saved hierarchy and content
        
        Args:
            hierarchy_file: Path to saved hierarchy JSON
            content_file: Path to saved content JSON
            key_word: Override key word (optional)
            
        Returns:
            Analysis results
        """
        print("\n" + "="*60)
        print("Running Gap Analysis from Saved Data")
        print("="*60 + "\n")
        
        # Load saved hierarchy
        print(f"Loading hierarchy from: {hierarchy_file}")
        with open(hierarchy_file, 'r') as f:
            hierarchy_data = json.load(f)
        
        hierarchy = DimensionHierarchy(
            key_word=hierarchy_data['key_word'],
            hierarchy_text=hierarchy_data['hierarchy_text']
        )
        hierarchy.structured = hierarchy_data['structured']
        
        # Load saved content
        print(f"Loading content from: {content_file}")
        with open(content_file, 'r') as f:
            content_data = json.load(f)
        
        content = ExtractedContent(
            url=content_data['url'],
            title=content_data['title'],
            meta_description=content_data['meta_description'],
            content_blocks=content_data['content_blocks']
        )
        
        # Use provided key_word or from hierarchy
        key_word = key_word or hierarchy.key_word
        
        # Run analysis
        print("\nAnalyzing content gaps...")
        analysis = self.analyzer.analyze(content, hierarchy, key_word)
        
        # Save results
        results = analysis.to_json()
        self._save_results(results)
        
        # Display summary
        self._display_summary(analysis)
        
        return results
    
    def _load_keywords_from_csv(self, csv_file: str) -> list:
        """Load keywords and AIO HTML from CSV"""
        import csv
        
        keywords_data = []
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Extract dimensions from AIO HTML
                dimensions = self.aio_extractor.extract_dimensions(row['aio_html'])
                
                kw_data = KeywordData(
                    keyword=row['keyword'],
                    aio_html=row['aio_html'],
                    raw_dimensions=dimensions
                )
                
                keywords_data.append(kw_data)
                print(f"  - Loaded '{row['keyword']}' with {len(dimensions)} dimensions")
        
        return keywords_data
    
    def _save_intermediate(self, filename: str, data: dict):
        """Save intermediate results"""
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  → Saved to {filepath}")
    
    def _save_results(self, results: dict):
        """Save final analysis results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gap_analysis_{timestamp}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Analysis saved to: {filepath}")
    
    def _display_summary(self, analysis: GapAnalysisResult):
        """Display analysis summary"""
        print("\n" + "="*60)
        print("ANALYSIS SUMMARY")
        print("="*60)
        
        print(f"\nOverall Score: {analysis.overall_score}/100")
        
        print(f"\nStrengths ({len(analysis.strengths)}):")
        for s in analysis.strengths:
            print(f"  ✓ {s}")
        
        print(f"\nWeaknesses ({len(analysis.weaknesses)}):")
        for w in analysis.weaknesses:
            print(f"  ✗ {w}")
        
        print(f"\nRecommendations ({len(analysis.recommendations)}):")
        for i, r in enumerate(analysis.recommendations, 1):
            print(f"  {i}. {r}")
        
        print("\nDimension Scores:")
        for ds in sorted(analysis.dimension_scores, key=lambda x: x.score):
            bar = "█" * (ds.score // 10) + "░" * (10 - ds.score // 10)
            print(f"  {ds.dimension_path:<40} [{bar}] {ds.score}/100")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Content Gap Analyser")
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Full analysis command
    full_parser = subparsers.add_parser('full', help='Run full analysis')
    full_parser.add_argument('key_word', help='Central keyword (e.g., "digital reporting")')
    full_parser.add_argument('keywords_file', help='CSV file with keywords and AIO HTML')
    full_parser.add_argument('target_url', help='URL to analyze')
    
    # Gap analysis only command
    gap_parser = subparsers.add_parser('gap', help='Run gap analysis from saved data')
    gap_parser.add_argument('hierarchy_file', help='Saved hierarchy JSON file')
    gap_parser.add_argument('content_file', help='Saved content JSON file')
    gap_parser.add_argument('--key-word', help='Override key word (optional)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    analyser = ContentGapAnalyser()
    
    if args.command == 'full':
        analyser.run_full_analysis(
            args.key_word,
            args.keywords_file,
            args.target_url
        )
    elif args.command == 'gap':
        analyser.run_gap_analysis_only(
            args.hierarchy_file,
            args.content_file,
            args.key_word
        )


if __name__ == "__main__":
    main()