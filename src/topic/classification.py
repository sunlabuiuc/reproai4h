from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
import re
import torch
import logging

@dataclass
class ClassifierConfig:
    """Configuration for the topic classifier"""
    device: str = "cuda:0"  # Default GPU device
    input_path: Path = Path("data/processed/combined_data.csv")
    output_path: Path = Path("data/processed/classified_data.csv")

class TopicClassifier:
    """Classifier for medical research topics using LLM"""
    
    CATEGORIES = {
        "Clinical Images": "Visual medical data such as X-rays, MRIs, CT scans, or other imaging techniques used for diagnosis or monitoring.",
        "Biosignals": "Electrical or chemical signals from the body, such as heart rate, brain activity, or muscle contractions.",
        "Biomedicine": "Molecular and cellular level studies, including genetics, protein analysis, or metabolic processes.",
        "E.H.R (Electronic Health Records)": "Digital versions of patients' medical history, including diagnoses, treatments, and administrative data."
    }
    
    GUIDELINES = """
Key Guidelines for Classification:
1. Data Type: Consider the primary type of data being analyzed or discussed (e.g., images, electrical signals, molecular data, or patient records).
2. Research Focus: Identify the main area of study (e.g., diagnostic imaging, physiological monitoring, molecular biology, or healthcare management).
3. Methodology: Look for specific techniques or tools mentioned (e.g., image processing, signal analysis, sequencing, or data mining).
4. Application: Consider the intended use of the research (e.g., diagnosis, treatment planning, drug discovery, or health system optimization).
5. Scale: Note the scale of the study (e.g., individual organs, whole-body systems, molecular level, or population-level data).
"""

    def __init__(self, config: ClassifierConfig, llm_pipeline):
        self.config = config
        self.llm_pipeline = llm_pipeline
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def generate_classification_prompt(self, title: str, abstract: str) -> str:
        """Generate a prompt for the LLM to classify the paper"""
        categories_text = "\n".join(
            [f"{i+1}. {cat}: {desc}" 
             for i, (cat, desc) in enumerate(self.CATEGORIES.items())]
        )
        
        prompt = f"""Given the following title and abstract, classify the text into one of the main categories based on the provided guidelines. If multiple categories seem applicable, choose the most relevant one.

Title: {title}

Abstract: {abstract}

Main Categories:
{categories_text}

{self.GUIDELINES}

Please provide your classification in the following format:
Category: [Main Category]

Classification:"""
        
        return prompt

    def extract_classification(self, text: str) -> str:
        """Extract the classification category from the LLM response"""
        categories = ["E.H.R", "Biosignals", "Biomedicine", "Clinical Images"]
        
        match = re.search(r"Category:\s*(.*)", text, re.IGNORECASE)
        if match:
            category = match.group(1).strip()
            for cat in categories:
                if cat.lower() in category.lower():
                    return cat
        
        return "Unknown"

    def classify_paper(self, row: pd.Series) -> str:
        """Classify a single paper using the LLM"""
        # Select appropriate title field based on venue
        title = row['cleaned_title'] if row['venue'] in ['ml4h', 'mlhc', 'chil'] else row['title']
        abstract = row['abstract']
        
        prompt = self.generate_classification_prompt(title, abstract)
        
        try:
            generated_text = self.llm_pipeline(
                prompt,
                max_new_tokens=100,
                temperature=0.1,
                do_sample=True
            )[0]['generated_text']
            
            classification = self.extract_classification(generated_text)
            return classification
            
        except Exception as e:
            self.logger.error(f"Error classifying paper {row['paper_id']}: {str(e)}")
            return "Unknown"

    def process_dataset(
        self,
        df: Optional[pd.DataFrame] = None,
        batch_size: int = 100
    ) -> pd.DataFrame:
        """Process the entire dataset, classifying papers in batches"""
        # Load data if not provided
        if df is None:
            try:
                df = pd.read_csv(self.config.input_path)
                self.logger.info(f"Loaded {len(df)} papers from {self.config.input_path}")
            except FileNotFoundError:
                self.logger.error(f"Could not find input file: {self.config.input_path}")
                return None

        total_papers = len(df)
        self.logger.info(f"Starting classification of {total_papers} papers")
        
        # Process in batches
        for i in range(0, total_papers, batch_size):
            batch_df = df.iloc[i:i + batch_size].copy()
            batch_df['topic'] = batch_df.apply(self.classify_paper, axis=1)
            df.iloc[i:i + batch_size, df.columns.get_loc('topic')] = batch_df['topic']
            
            self.logger.info(f"Processed {min(i + batch_size, total_papers)}/{total_papers} papers")
            
            # Periodically save progress
            if (i + batch_size) % 1000 == 0 or (i + batch_size) >= total_papers:
                df.to_csv(self.config.output_path, index=False)
                self.logger.info(f"Saved progress to {self.config.output_path}")

        # Print classification summary
        self.logger.info("\nClassification Summary:")
        self.logger.info(df['topic'].value_counts())
        
        return df

# Example usage:
# def main():
#     # Initialize config
#     config = ClassifierConfig(
#         device="cuda:1",
#         input_path=Path("data/processed/combined_data.csv"),
#         output_path=Path("data/processed/classified_data.csv")
#     )
    
#     # Initialize LLM (assuming load_70b_model is imported)
#     device = torch.device(config.device if torch.cuda.is_available() else "cpu")
#     llm_pipeline = load_70b_model(device)
    
#     # Initialize and run classifier
#     classifier = TopicClassifier(config, llm_pipeline)
#     classified_df = classifier.process_dataset(batch_size=100)
    
#     if classified_df is not None:
#         print("\nClassification Results:")
#         print(classified_df[['title', 'topic']].head())
#         print("\nTopic Distribution:")
#         print(classified_df['topic'].value_counts())

# if __name__ == "__main__":
#     main()