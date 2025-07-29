# utils/csv_parser.py
import csv
import json
from typing import List
from models.data_models import KeywordData
import pdb

def parse_keywords_csv(file_content: str) -> List[KeywordData]:
    """Parse CSV with keyword and AIO JSON structure"""
    keywords_data = []
    
    # Parse CSV
    #pdb.set_trace()
    reader = csv.DictReader(file_content.splitlines())
    
    for row in reader:
        keyword = row['Keyword']
        aio_json_str = row['Aio']
        
        try:
            # Parse the JSON structure
            aio_data = json.loads(aio_json_str)
            
            # Extract HTML from the nested structure
            aio_html = aio_data['aio']['html']
            
            # Create KeywordData object
            kw_data = KeywordData(
                keyword=keyword,
                aio_html=aio_html,
                raw_dimensions=[]  # Will be populated by extractor
            )
            
            keywords_data.append(kw_data)
            
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Error parsing AIO data for keyword '{keyword}': {str(e)}")
    
    return keywords_data