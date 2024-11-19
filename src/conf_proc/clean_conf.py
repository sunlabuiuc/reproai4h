import transformers
import torch
from transformers import BitsAndBytesConfig, pipeline, AutoTokenizer
from src.conf_proc.pathing import ConferencePathManager
import pandas as pd

class ConferencePaperCleaner:
    def __init__(self, path_manager: ConferencePathManager, device="cuda:0"):
        self.path_manager = path_manager
        self.device = device
        self.title_cleaning_prompt = """
        You are an assistant specialized in cleaning and standardizing academic paper titles. Your task is to take a given title and improve its formatting, spacing, and consistency. Follow these rules:

        1. Correct spacing:
           - Ensure single spaces between words.
           - Remove extra spaces before or after hyphens.
           - Add spaces after colons and semicolons.

        2. Hyphenation:
           - Use hyphens consistently in compound terms (e.g., "Multi-Scale" not "Multi Scale" or "MultiScale").
           - Correct common hyphenation errors in technical terms (e.g., "Pre-processing" not "Preprocessing").

        3. Capitalization:
           - Use title case: Capitalize the first letter of each major word.
           - Do not capitalize articles (a, an, the), coordinating conjunctions (and, but, for, or, nor), or prepositions unless they start the title.
           - Always capitalize the first and last words of the title and subtitle.

        4. Acronyms and initialisms:
           - Remove spaces between letters in acronyms (e.g., "CNN" not "C N N").
           - Ensure correct formatting of technical acronyms (e.g., "U-Net" not "UNet" or "U Net").

        5. Special characters:
           - Correct the use of special characters like hyphens (-), en dashes (–), and em dashes (—).
           - Ensure proper use of quotation marks and apostrophes.

        6. Consistency:
           - Maintain consistent formatting throughout the title.
           - Ensure that similar terms or concepts are formatted the same way.

        7. Grammar and spelling:
           - Correct any obvious spelling errors.
           - Ensure proper grammatical structure.

        8. No Authors: If the title contains any author names, emails, or affiliations, remove them.

        Title to clean: {title}

        Cleaned title:
        """
        self.model = self._load_70b_model()

    def _load_70b_model(self):
        # Import your load_70b_model function or implement it here
        from src.llm.llm import load_70b_model
        return load_70b_model(self.device)

    def _generate_text_with_icl(self, prompt, examples, max_new_tokens=256, temperature=0.00001, top_p=0.99):
        # Import your generate_text_with_icl function or implement it here
        from src.llm.llm import generate_text_with_icl
        return generate_text_with_icl(prompt, self.model, examples, max_new_tokens, temperature, top_p)

    def extract_and_clean_emails(self, text):
        prompt = f"""
        Extract all email addresses from the following text.
        Clean the extracted email addresses by removing any unnecessary characters or formatting issues.
        Output only the cleaned email addresses, one per line.
        
        Text: {text}
        
        Cleaned and extracted email addresses:
        """
        return self._generate_text_with_icl(prompt, [{"input": text, "output": ""}])

    def process_dataframe_emails(self, df: pd.DataFrame, text_column: str):
        processed_emails = df[text_column].apply(lambda x: self.extract_and_clean_emails(x))
        
        new_df = df.copy()
        new_df['processed_emails'] = processed_emails
        
        cols = list(new_df.columns)
        text_index = cols.index(text_column)
        cols.insert(text_index + 1, cols.pop(cols.index('processed_emails')))
        new_df = new_df[cols]
        
        return new_df

    def clean_titles(self, df: pd.DataFrame):
        cleaned_titles = []
        for title in df["title"]:
            formatted_prompt = self.title_cleaning_prompt.format(title=title)
            cleaned_title = self._generate_text_with_icl(formatted_prompt, [{"input": formatted_prompt, "output": ""}])
            print(cleaned_title)
            cleaned_titles.append(cleaned_title)
        return cleaned_titles

    def process_dataframe_titles(self, df: pd.DataFrame):
        cleaned_titles = self.clean_titles(df)
        
        new_df = df.copy()
        new_df['cleaned_title'] = cleaned_titles
        
        cols = list(new_df.columns)
        title_index = cols.index('title')
        cols.insert(title_index + 1, cols.pop(cols.index('cleaned_title')))
        new_df = new_df[cols]
        
        return new_df

    def clean_conference_papers(self, conference: str):
        """Clean conference papers with simple debug mode"""
        conf = self.path_manager.get_conference_config(conference)
        
        # Read input file
        input_file = self.path_manager.get_output_filename(
            conference,
            year=conf.debug_year if self.path_manager.debug else None,
            stage='processed'
        )
        print(f"Reading input file: {input_file}")
        
        df = pd.read_csv(input_file)
        
        # In debug mode, just take first 5 papers
        if self.path_manager.debug:
            df = df.head(5)
            print(f"Debug mode: Processing first {len(df)} papers")
        
        # Process papers
        print(f"Cleaning {len(df)} papers...")
        cleaned_df = self.process_dataframe_titles(df)
        cleaned_df = self.process_dataframe_emails(cleaned_df, "authors")
        
        # Save results
        output_file = self.path_manager.get_output_filename(
            conference,
            year=conf.debug_year if self.path_manager.debug else None,
            stage='cleaned'
        )
        cleaned_df.to_csv(output_file, index=False)
        print(f"Wrote cleaned data to {output_file}")

