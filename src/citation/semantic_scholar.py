from dataclasses import dataclass
import os
import requests
import time
import pandas as pd
from typing import Dict, Optional, List
import logging

@dataclass
class SemanticScholarConfig:
    api_key: str
    base_url: str = 'https://api.semanticscholar.org/graph/v1/paper/search'
    result_limit: int = 10
    delay: float = 2.2
    max_retries: int = 3

class SemanticScholarProcessor:
    def __init__(self, config: Optional[SemanticScholarConfig] = None):
        self.config = config or SemanticScholarConfig(
            api_key=os.getenv('S2_API_KEY', '')
        )
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def search_papers(self, query: str) -> List[Dict]:
        """Search for papers using the Semantic Scholar API"""
        params = {
            'query': query,
            'limit': self.config.result_limit,
            'fields': 'title,url,abstract,authors,year,citationCount'
        }
        headers = {'X-API-KEY': self.config.api_key}
        retry_delay = self.config.delay

        for attempt in range(self.config.max_retries):
            try:
                response = requests.get(
                    self.config.base_url, 
                    params=params, 
                    headers=headers
                )
                response.raise_for_status()
                results = response.json()
                time.sleep(self.config.delay)
                
                if 'data' in results:
                    return results['data']
                return []
                    
            except requests.RequestException as e:
                if response.status_code == 429:
                    self.logger.warning(f"Rate limit exceeded. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    self.logger.error(f"An error occurred: {e}")
                    return []
        
        return []

    def get_citation_count(self, title: str, n_words: int = 3) -> Optional[int]:
        """Get citation count for a paper by matching title"""
        papers = self.search_papers(title)
        
        if not papers:
            self.logger.debug(f"No papers found for title: {title}")
            return None

        title_words = title.lower().split()
        for paper in papers:
            paper_title_words = paper['title'].lower().split()
            
            for i in range(len(title_words) - n_words + 1):
                if ' '.join(title_words[i:i+n_words]) in ' '.join(paper_title_words):
                    return paper['citationCount']
        
        self.logger.debug(f"No matching paper found for title: {title}")
        return None

    def process_conferences(self, file_paths: Dict[str, Dict[str, str]]) -> Dict[str, pd.DataFrame]:
        """
        Process conferences using provided file paths
        
        Args:
            file_paths: Dictionary of conference names to input/output paths
                       {'conference': {'input': 'path/to/input.csv', 
                                     'output': 'path/to/output.csv'}}
        """
        results = {}
        
        for conference, paths in file_paths.items():
            try:
                df = pd.read_csv(paths['input'])
                self.logger.info(f"Processing {len(df)} papers from {conference}")

                # Add citation counts
                df['citation_count'] = df['cleaned_title'].apply(self.get_citation_count)
                
                # Save results
                df.to_csv(paths['output'], index=False)
                self.logger.info(f"Saved citation data to {paths['output']}")
                
                # Log summary statistics
                self.logger.info(f"\n{conference.upper()} Citation Summary:")
                self.logger.info(df['citation_count'].describe())
                self.logger.info(f"Papers without citations: {df['citation_count'].isna().sum()}")
                
                results[conference] = df
                
                # Add delay between conferences
                time.sleep(self.config.delay)
                
            except FileNotFoundError:
                self.logger.error(f"Could not find data file: {paths['input']}")
                continue
        
        return results

# Example usage:
def main():
    # Define file paths
    file_paths = {
        'ml4h': {
            'input': 'data/cleaned/ml4h/ml4h_cleaned.csv',
            'output': 'data/processed/ml4h/ml4h_citations.csv'
        },
        'chil': {
            'input': 'data/cleaned/chil/chil_cleaned.csv',
            'output': 'data/processed/chil/chil_citations.csv'
        },
        'mlhc': {
            'input': 'data/cleaned/mlhc/mlhc_cleaned.csv',
            'output': 'data/processed/mlhc/mlhc_citations.csv'
        }
    }
    
    # Initialize processor
    processor = SemanticScholarProcessor(
        SemanticScholarConfig(api_key="YOUR_API_KEY")
    )
    
    # Process all conferences
    conference_dfs = processor.process_conferences(file_paths)
    
    # Use the returned dataframes for next steps
    for conf, df in conference_dfs.items():
        print(f"\n{conf} shape:", df.shape)

if __name__ == "__main__":
    main()