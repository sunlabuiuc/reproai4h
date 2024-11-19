import os
import PyPDF2
import json
import re
import spacy
import csv
from src.conf_proc.pathing import ConferencePathManager
from collections import defaultdict, Counter

class PDFContentProcessor:
    def __init__(self, path_manager: ConferencePathManager):
        self.path_manager = path_manager
        # ... rest of initialization
        # Load the transformer-based model
        self.nlp = spacy.load("en_core_web_trf")
        
        # Initialize dataset terms
        self.dataset_terms = [
            ["MIMIC", "Medical Information Mart for Intensive Care"],
            ["eICU", "eICU Collaborative Research Database"],
            ["UK Biobank"],
            ["Chest X-Ray14", "NIH Chest X-ray"],
            ["ADNI", "Alzheimer's Disease Neuroimaging Initiative"],
            ["PhysioNet"],
            ["OASIS", "Open Access Series of Imaging Studies"],
            ["TCGA", "The Cancer Genome Atlas Program"],
            ["GDC", "Genomic Data Commons"],
            ["SEER", "Surveilance Epidemiology and End Results"],
            ["TUH EEG Corpus", "TUEG"],
            ["TUH Abnormal EEG Corpus", "TUAB"],
            ["TUH EEG Artifact Corpus", "TUAR"],
            ["TUH EEG Epilepsy Corpus", "TUEP"],
            ["TUH EEG Events Corpus", "TUEV"],
            ["TUH EEG Seizure Corpus", "TUSV"],
            ["TUH EEG Slowing Corpus", "TUSL"]
        ]
        self.dataset_mapping = self._create_dataset_mapping()
        self.conferences = {
            "CHIL": ["chil/2020pdf", "chil/2021pdf", "chil/2022pdf", "chil/2023pdf", "chil/2024pdf"],
            "ML4H": ["ml4h/2019pdf", "ml4h/2020pdf", "ml4h/2021pdf", "ml4h/2022pdf", "ml4h/2023pdf"],
            "MLHC": ["mlhc/2017pdf", "mlhc/2018pdf", "mlhc/2019pdf", "mlhc/2020pdf", 
                    "mlhc/2021pdf", "mlhc/2022pdf", "mlhc/2023pdf"]
        }

    def _create_dataset_mapping(self):
        """Create mapping of dataset terms"""
        mapping = {}
        for term_group in self.dataset_terms:
            key = term_group[0].lower().replace(' ', '_')
            mapping[key] = [term.lower() for term in term_group]
        return mapping

    def extract_pdf_content(self, filename):
        """Extract content from PDF file up to references section"""
        try:
            with open(filename, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                text = ""
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    text += page_text
                    
                    if re.search(r'\n(References|Bibliography|Works Cited|Literature Cited)', 
                               page_text, re.IGNORECASE):
                        split_text = re.split(r'\n(References|Bibliography|Works Cited|Literature Cited)', 
                                           text, maxsplit=1, flags=re.IGNORECASE)
                        text = split_text[0]
                        break
            return text
        except Exception as e:
            print(f"Error extracting content from {filename}: {str(e)}")
            return None

    def is_likely_name(self, text):
        """Check if text likely contains a person's name"""
        doc = self.nlp(text)
        return any(ent.label_ == "PERSON" for ent in doc.ents)

    def clean_title(self, title):
        """Clean and standardize paper title"""
        # Remove all spaces
        title = re.sub(r'\s', '', title)
        
        # Remove proceedings information
        title = re.sub(r'Proceedingsof.*?20\d{2}', '', title, flags=re.IGNORECASE)
        
        # Remove conference names and years
        conferences = [
            'MachineLearningforHealthcare', 'MachineLearningforHealth', 'ML4H',
            'ClinicalAbstract,Software,andDemoTrack', 'ConferenceonHealth,Inference,andLearning',
            'CHIL', 'MLHC', 'NeurIPS', 'MachineLearningforHealthcare',
            'ProceedingsofMachineLearningResearch', 
            '1–26,2 0 1 8 M a c h i n eL e r gf o rH l t',
            'M a c h i n eL e r gf o rH l t '
        ]
        
        for conf in conferences:
            title = re.sub(rf'{conf}.*?20\d{{2}}', '', title, flags=re.IGNORECASE)
            title = re.sub(rf'{conf}', '', title, flags=re.IGNORECASE)
        
        # Additional cleaning steps
        title = re.sub(r'Workshop', '', title, flags=re.IGNORECASE)
        title = re.sub(r'20\d{2}', '', title)
        title = re.sub(r'\d+[-–]\d+,?20\d{2}', '', title)
        title = re.sub(r'^[\d\W]+|[\d\W]+$', '', title)
        title = re.sub(r'(?<!^)(?=[A-Z])', ' ', title)
        
        # Remove duplicate words
        words = title.split()
        title = ' '.join(word for i, word in enumerate(words) 
                        if word.lower() not in [w.lower() for w in words[:i]])
        
        return title.strip()

    def extract_title(self, lines):
        """Extract paper title from text lines"""
        title_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if self.is_likely_name(line):
                break
            title_lines.append(line)

        title = ' '.join(title_lines)
        title = re.sub(r'\s+', ' ', title).strip()
        title = re.sub(r'^[^a-zA-Z]+', '', title)
        return self.clean_title(title)

    def extract_authors(self, lines):
        """Extract author information from text lines"""
        authors = []
        author_section_started = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if 'ABSTRACT' in line.upper():
                break
            if self.is_likely_name(line) or '@' in line:
                author_section_started = True
                authors.append(line)
            elif author_section_started:
                authors.append(line)
            if len(authors) > 15:
                break
        return authors

    def extract_abstract(self, text):
        """Extract abstract from paper text"""
        abstract_start = re.search(r'\bABSTRACT\b', text, re.IGNORECASE)
        if not abstract_start:
            return ""
        
        intro_start = re.search(r'\b(1\s*\.?\s*)?INTRODUCTION\b', 
                              text[abstract_start.end():], re.IGNORECASE)
        
        if intro_start:
            abstract = text[abstract_start.end():abstract_start.end() + intro_start.start()]
        else:
            abstract = text[abstract_start.end():abstract_start.end() + 2000]
        
        return re.sub(r'\s+', ' ', abstract).strip()

    def count_mentions(self, text, terms):
        """Count mentions of terms in text"""
        if text is None:
            return 0
        text = text.lower()
        return sum(1 for term in terms if term.lower() in text)


    def process_pdf(self, content):
        """Process PDF content and extract relevant information"""
        lines = content.split('\n')
        title = self.extract_title(lines)
        authors = self.extract_authors(lines)
        abstract = self.extract_abstract(content)
        
        result = {
            'title': title,
            'authors': authors,
            'abstract': abstract,
            'code_count': self.count_mentions(content, ['github', "gitlab", "zenodo", "colab"]),
            'gitlab_count': self.count_mentions(content, ['gitlab']),
            'zenodo_count': self.count_mentions(content, ['Zenodo']),
        }
        
        for key, terms in self.dataset_mapping.items():
            result[f"{key}_count"] = self.count_mentions(content, terms)
        
        result['dataset_count'] = sum(result[f"{key}_count"] for key in self.dataset_mapping)
        return result

    def process_directory(self, directory, year):
        """Process all PDFs in a directory"""
        results = []
        for filename in os.listdir(directory):
            if filename.endswith('.pdf'):
                filepath = os.path.join(directory, filename)
                content = self.extract_pdf_content(filepath)
                
                if content:
                    result = self.process_pdf(content)
                    result['year'] = year
                    result['filename'] = filename
                    results.append(result)
                    print(f"Processed {filename}")
        return results

    def process_conference(self, conference: str):
        """Process conference papers with simple debug mode"""
        conf = self.path_manager.get_conference_config(conference)
        years = conf.get_years(self.path_manager.debug)
        
        all_results = []
        for year in years:
            paths = self.path_manager.get_paths(conference, year)
            print(f"\nProcessing {conference} papers from {year}")
            
            # Get list of PDFs and limit if in debug mode
            pdf_files = list(paths['year_pdfs'].glob('*.pdf'))
            if self.path_manager.debug:
                pdf_files = pdf_files[:5]
                print(f"Debug mode: Processing first {len(pdf_files)} papers")
                
            for pdf_file in pdf_files:
                content = self.extract_pdf_content(pdf_file)
                if content:
                    result = self.process_pdf(content)
                    result['year'] = year
                    result['filename'] = pdf_file.name
                    all_results.append(result)
                    print(f"Processed {pdf_file.name}")
        
        # Save results
        output_file = self.path_manager.get_output_filename(
            conference,
            year=conf.debug_year if self.path_manager.debug else None,
            stage='processed'
        )
        self.write_to_csv(all_results, output_file)
        print(f"Wrote {len(all_results)} results to {output_file}")
                        
    def write_to_csv(self, results, filename):
        """Write extracted information to CSV file"""
        fieldnames = ['year', 'title', 'authors', 'abstract', 'code_count', 
                     'gitlab_count', 'zenodo_count', 'dataset_count']
        fieldnames.extend([f"{key}_count" for key in self.dataset_mapping])
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, 
                                  quoting=csv.QUOTE_ALL, escapechar='\\')
            writer.writeheader()
            
            for result in results:
                try:
                    row = {
                        'year': result['year'],
                        'title': result['title'],
                        'authors': ', '.join(result['authors']),
                        'abstract': result['abstract'],
                        'code_count': result['code_count'],
                        'gitlab_count': result['gitlab_count'],
                        'zenodo_count': result['zenodo_count'],
                        'dataset_count': result['dataset_count']
                    }
                    
                    for key in self.dataset_mapping:
                        row[f"{key}_count"] = result[f"{key}_count"]
                    
                    # Clean string fields
                    for key, value in row.items():
                        if isinstance(value, str):
                            row[key] = value.replace('\n', ' ').replace('\r', '')
                    
                    writer.writerow(row)
                except Exception as e:
                    print(f"Error writing row: {e}")
                    print(f"Problematic row: {result}")
                    continue