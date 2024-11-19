# We note that there was a lot of post-processing steps that we did after we back-analyzed some incorrect papers and issues with that in the notebooks.



from dataclasses import dataclass
from pathlib import Path
from typing import Dict
import torch
import pandas as pd
import logging
from src.topic.classification import ClassifierConfig, TopicClassifier
from src.llm.llm import load_70b_model
@dataclass
class DataPaths:
    """Paths for input and output data files"""
    pubmed_path: Path
    ml4h_path: Path
    chil_path: Path
    mlhc_path: Path
    output_path: Path

class DataMerger:
    def __init__(self, paths: DataPaths):
        self.paths = paths
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def read_data(self) -> Dict[str, pd.DataFrame]:
        """Read all input dataframes"""
        dfs = {}
        
        # Read conference data
        for name, path in [
            ('ml4h', self.paths.ml4h_path),
            ('chil', self.paths.chil_path),
            ('mlhc', self.paths.mlhc_path),
            ('pubmed', self.paths.pubmed_path)
        ]:
            try:
                df = pd.read_csv(path)
                self.logger.info(f"Read {name} data: {len(df)} rows")
                dfs[name] = df
            except FileNotFoundError:
                self.logger.error(f"Could not find {name} data at {path}")
                return None
        
        return dfs

    def standardize_columns(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        """Standardize columns for a dataframe"""
        # Ensure required columns exist
        required_columns = [
            'year', 'paper_id', 'title', 'cleaned_title', 'authors', 
            'abstract', 'citation_count', 'code', 'ai'
        ]
        
        for col in required_columns:
            if col not in df.columns:
                if col in ['code', 'ai']:
                    df[col] = 0
                elif col in ['citation_count', 'year']:
                    df[col] = 0
                else:
                    df[col] = ''
        
        # Convert numeric columns
        numeric_cols = ['year', 'citation_count', 'code', 'ai']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        
        # Add venue if not present
        if 'venue' not in df.columns:
            df['venue'] = source
        
        # Ensure string columns are strings
        string_cols = ['paper_id', 'title', 'cleaned_title', 'authors', 'abstract', 'venue']
        for col in string_cols:
            df[col] = df[col].fillna('').astype(str)
            
        return df

    def merge_data(self) -> pd.DataFrame:
        """Merge all dataframes"""
        # Read all data
        dfs = self.read_data()
        if not dfs:
            return None
        
        # Standardize each dataframe
        standardized_dfs = {}
        for source, df in dfs.items():
            standardized_dfs[source] = self.standardize_columns(df, source)
            self.logger.info(f"Standardized {source} data: {len(standardized_dfs[source])} rows")
        
        # Combine all dataframes
        merged_df = pd.concat(standardized_dfs.values(), ignore_index=True)
        self.logger.info(f"Combined data: {len(merged_df)} rows")
        
        # Save merged data
        merged_df.to_csv(self.paths.output_path, index=False)
        self.logger.info(f"Saved combined data to {self.paths.output_path}")
        
        return merged_df

# Example usage:
def main():
    # Define all paths
    paths = DataPaths(
        pubmed_path=Path("data/processed/pubmed_stats.csv"),
        ml4h_path=Path("data/processed/ml4h/ml4h_citations.csv"),
        chil_path=Path("data/processed/chil/chil_citations.csv"),
        mlhc_path=Path("data/processed/mlhc/mlhc_citations.csv"),
        output_path=Path("data/processed/combined_data.csv")
    )
    
    # Initialize merger and process data
    merger = DataMerger(paths)
    combined_df = merger.merge_data()
    

    # Initialize config
    config = ClassifierConfig(
        device="cuda:1",
        input_path=Path("data/processed/combined_data.csv"),
        output_path=Path("data/processed/classified_data.csv")
    )
    
    # Initialize LLM (assuming load_70b_model is imported)
    device = torch.device(config.device if torch.cuda.is_available() else "cpu")
    llm_pipeline = load_70b_model(device)
    
    # Initialize and run classifier
    classifier = TopicClassifier(config, llm_pipeline)
    classified_df = classifier.process_dataset(batch_size=100)
    
    # Topic Classification saved below
    if classified_df is not None:
        print("\nClassification Results:")
        print(classified_df[['title', 'topic']].head())
        print("\nTopic Distribution:")
        print(classified_df['topic'].value_counts())


    if combined_df is not None:
        print("\nFinal Dataset Summary:")
        print(f"Total rows: {len(combined_df)}")
        print(f"Venues: {combined_df['venue'].value_counts()}")
        print(f"Years: {combined_df['year'].value_counts().sort_index()}")
    # To: data/processed/classified_data.csv

if __name__ == "__main__":
    main()