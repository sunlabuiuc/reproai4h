import pandas as pd 
import pickle 
import csv
import json
import pmidcite
import requests
import time
import metapub as mp
import os
from typing import Dict, List, Any, Tuple, Optional, Union
from pmidcite.icite.downloader import get_downloader
from src.pubmed.pmc_scrape_func import (
    parse_bioc_xml, 
    parse_bioc_xml_year, 
    parse_bioc_xml_abstract, 
    parse_bioc_xml_authors, 
    parse_bioc_xml_title
)

class PubMedProcessor:
    def __init__(self, venue: str = "pubmed"):
        """
        Initialize the PubMed processor with venue and citation downloader.
        
        Args:
            venue (str): The venue to process ('pubmed' or 'amia')
        """
        self.venue = venue
        print(f"pmidcite version: {pmidcite.__version__}")
        self.dnldr = get_downloader()
        self.dataset_mapping = {}
        
        # Create necessary directories
        os.makedirs(f"{venue}_content", exist_ok=True)
        os.makedirs("processed_data", exist_ok=True)

    def get_citation_count(self, pmid: str) -> int:
        """Get citation count for a given PMID."""
        nih_entry = self.dnldr.get_icite(pmid)
        nih_dict = nih_entry.get_dict()
        return nih_dict["citation_count"]

    def pmid2biocxml(self, pmid: Union[str, List[str]]) -> List[str]:
        """Fetch BioC XML for given PMIDs."""
        start_time = time.time()
        base_url = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/{pmid}/unicode"
        
        if not isinstance(pmid, list):
            pmid = [pmid]
            
        res = []
        api_status = "up"
        
        for pmid_ in pmid:
            request_url = base_url.format(pmid=pmid_)
            try:
                response = requests.get(request_url, timeout=10)
                response.raise_for_status()
                res.append(response.text)
                print(f"PMID {pmid_}: Response length = {len(response.text)} characters")
            except requests.exceptions.RequestException as e:
                print(f"Error accessing the API for PMID {pmid_}: {str(e)}")
                api_status = "down"
                break
                
        end_time = time.time()
        print(f"pmid2biocxml execution time: {end_time - start_time:.2f} seconds")
        print(f"API Status: {'Up' if api_status == 'up' else 'Down'}")
        return res

    @staticmethod
    def read_pmids_from_csv(filename: str) -> List[str]:
        """Read PMIDs from CSV file."""
        start_time = time.time()
        pmids = []
        with open(filename, 'r') as csvfile:
            reader = csv.reader(csvfile)
            next(reader)  # Skip header
            pmids = [row[0] for row in reader]
        end_time = time.time()
        print(f"read_pmids_from_csv execution time: {end_time - start_time:.2f} seconds")
        return pmids

    @staticmethod
    def flatten_passages(bioc_dict: Dict) -> str:
        """Flatten passage content into single string."""
        return " ".join(section["content"] for section in bioc_dict["passage"])

    def process_bioc_xml(self, bioc_xmls: List[str], read_pmids: List[str]) -> Dict:
        """Process BioC XML data into structured dictionary."""
        pubmed_dates = [parse_bioc_xml_year(xml) for xml in bioc_xmls]
        
        my_processed_dict = {}
        parse_start_time = time.time()
        
        for idx, bioc_xml in enumerate(bioc_xmls):
            pmid = read_pmids[idx]
            year = pubmed_dates[idx]
            print(f"Processing {self.venue.upper()} ID:", pmid)
            
            if isinstance(bioc_xml, str) and len(bioc_xml) > 0 and "xml" in bioc_xml:
                dictionary = parse_bioc_xml(bioc_xml)
                my_processed_dict[pmid] = {
                    "content": self.flatten_passages(dictionary),
                    "year": year,
                    "title": parse_bioc_xml_title(bioc_xml),
                    "authors": parse_bioc_xml_authors(bioc_xml),
                    "abstract": parse_bioc_xml_abstract(bioc_xml)
                }
            else:
                print(f"Warning: Empty or invalid BioC XML for {self.venue.upper()} ID {pmid}")
        
        parse_end_time = time.time()
        print(f"parse_bioc_xml execution time: {parse_end_time - parse_start_time:.2f} seconds")
        return my_processed_dict

    def get_papers_year(self, dictionary: Dict, year: str) -> Dict:
        """Filter papers by year."""
        return {
            pmid: record for pmid, record in dictionary.items()
            if record["year"] == year
        }

    @staticmethod
    def count_mentions(text: Optional[str], terms: List[str]) -> int:
        """Count mentions of terms in text."""
        if text is None:
            return 0
        text = text.lower()
        return sum(1 for term in terms if term.lower() in text)

    def create_dataset_mapping(self, dataset_terms: List[List[str]]) -> Dict:
        """Create mapping of dataset terms."""
        self.dataset_mapping = {
            term_group[0].lower().replace(' ', '_'): [term.lower() for term in term_group]
            for term_group in dataset_terms
        }
        return self.dataset_mapping

    def count_mentions_grouped(self, text: Optional[str]) -> Dict:
        """Count mentions of grouped terms in text."""
        if text is None:
            return {key: 0 for key in self.dataset_mapping}
        text = text.lower()
        return {
            key: sum(1 for term in terms if term in text)
            for key, terms in self.dataset_mapping.items()
        }

    def get_counts_per_paper(self, year_papers: Dict) -> Dict:
        """Get counts of various metrics per paper."""
        counts = {}
        code_terms = ["github", "gitlab", "zenodo", "colab", "bitbucket", "docker", "jupyter", "kaggle"]
        
        for pmid, record in year_papers.items():
            text = record["content"]
            dataset_counts = self.count_mentions_grouped(text)
            
            counts[pmid] = {
                **dataset_counts,
                "big_datasets": sum(dataset_counts.values()),
                "code": self.count_mentions(text, code_terms),
                "ai": self.count_mentions(text, [
                    "AI", "Artificial Intelligence", "Machine Learning",
                    "Deep Learning", "Neural Network"
                ]),
                "citation_count": self.get_citation_count(pmid)
            }
            print(counts[pmid])
        return counts

    def get_analysis(self, counts: Dict) -> Dict:
        """Generate analysis statistics from counts."""
        stats = {
            'total_files': len(counts),
            'files_with_github': sum(1 for r in counts.values() if r['code'] > 0),
            'files_without_github': sum(1 for r in counts.values() if r['code'] == 0),
            'total_github_mentions': sum(r['code'] for r in counts.values()),
            'files_with_public_dataset': sum(1 for r in counts.values() if r['big_datasets'] > 0),
            'total_dataset_mentions': sum(r['big_datasets'] for r in counts.values()),
            'files_with_github_and_dataset': sum(1 for r in counts.values() if r['code'] > 0 and r['big_datasets'] > 0),
            'files_with_github_and_without_dataset': sum(1 for r in counts.values() if r['code'] > 0 and r['big_datasets'] == 0),
            'files_with_AI': sum(1 for r in counts.values() if r['ai'] > 0),
            'total_citations': sum(r['citation_count'] for r in counts.values() if r['citation_count'] is not None),
        }
        
        # Add dataset-specific statistics
        for key in self.dataset_mapping.keys():
            stats[f'files_with_{key}'] = sum(1 for r in counts.values() if r[key] > 0)
            stats[f'total_{key}_mentions'] = sum(r[key] for r in counts.values())
        
        return stats

    def analyze_papers_across_years(self, dictionary: Dict, years: List[str]) -> Tuple[Dict, Dict]:
        """Analyze papers across multiple years."""
        all_stats = {}
        all_paper_data = {}
        
        for year in years:
            papers = self.get_papers_year(dictionary, year)
            counts_each_paper = self.get_counts_per_paper(papers)
            analysis = self.get_analysis(counts_each_paper)
            
            all_stats[year] = analysis 
            all_paper_data[year] = counts_each_paper
            
            print(f"Year: {year}, Papers: {len(papers)}")
            print(analysis)
            
        return all_stats, all_paper_data

    def save_results(self, all_stats: Dict, all_paper_data: Dict, bioc_dicts: Dict) -> None:
        """Save analysis results to files."""
        csv_file_path = f"data/processed/{self.venue}_stats.csv"
        # Save stats to CSV
        self.write_stats_to_csv(all_stats, 
                              csv_file_path)
        

        # Save paper data with full information
        self.save_paper_data(all_paper_data, 
                           f"data/processed/{self.venue}_paper_data.json",
                           f"data/processed/{self.venue}_paper_data.pkl",
                           bioc_dicts)

        return csv_file_path
    
    def write_stats_to_csv(self, all_stats: Dict, filename: str) -> None:
        """Write analysis statistics to CSV file."""
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            header = ['Statistic'] + list(all_stats.keys())
            writer.writerow(header)
            
            stats_keys = [
                'total_files', 
                'files_with_github', 'files_without_github', 'total_github_mentions',
                'files_with_public_dataset', 'total_dataset_mentions',
                'files_with_github_and_dataset',
                'files_with_github_and_without_dataset',
                'files_with_AI',
                'total_citations'
            ]
            
            for key in self.dataset_mapping.keys():
                stats_keys.extend([f'files_with_{key}', f'total_{key}_mentions'])
            
            for key in stats_keys:
                row = [key.replace('_', ' ').title()]
                for year in all_stats.keys():
                    row.append(all_stats[year].get(key, ''))
                writer.writerow(row)

    def save_paper_data(self, all_paper_data: Dict, json_filename: str, 
                       pkl_filename: str, bioc_dicts: Dict) -> None:
        """Save paper data to JSON and pickle files with full information."""
        full_paper_data = {
            year: {
                pmid: {
                    **data,
                    "title": bioc_dicts[pmid]["title"],
                    "authors": bioc_dicts[pmid]["authors"],
                    "abstract": bioc_dicts[pmid]["abstract"]
                }
                for pmid, data in papers.items()
            }
            for year, papers in all_paper_data.items()
        }
        
        with open(json_filename, 'w') as f:
            json.dump(full_paper_data, f, indent=4)
        
        with open(pkl_filename, 'wb') as f:
            pickle.dump(full_paper_data, f)

    @staticmethod
    def save_to_pickle(data: Any, filename: str) -> None:
        """Save data to pickle file."""
        with open(filename, 'wb') as f:
            pickle.dump(data, f)

    @staticmethod
    def load_from_pickle(filename: str) -> Any:
        """Load data from pickle file."""
        with open(filename, 'rb') as f:
            return pickle.load(f)

    def process_venue(self, n: int = 10000, filename = "") -> None:
        """
        Process the entire venue workflow.
        
        Args:
            n (int): Number of PMIDs to process
        """
        start_time = time.time()
        print(f"Starting BioC scraping for venue: {self.venue.upper()}")

        # Step 1: Read PMIDs and fetch BioC XML
        # filename = f"{self.venue}_ai_ml_pmids.csv"
        read_pmids = self.read_pmids_from_csv(filename)
        bioc_xmls = self.pmid2biocxml(read_pmids[:n])
        self.save_to_pickle(bioc_xmls, f"data/raw/{self.venue}/bioc_xmls.pkl")

        # Step 2: Process BioC XML
        bioc_xmls = self.load_from_pickle(f"data/raw/{self.venue}/bioc_xmls.pkl")
        my_processed_dict = self.process_bioc_xml(bioc_xmls, read_pmids[:n])
        self.save_to_pickle(my_processed_dict, f"data/raw/{self.venue}/paper_content_flattened.pkl")

        # Step 3: Analyze processed data
        bioc_dicts = self.load_from_pickle(f"data/raw/{self.venue}/paper_content_flattened.pkl")
        print(f"Processed {len(bioc_dicts)} papers")
        
        years = ["2018", "2019", "2020", "2021", "2022", "2023", "2024"]
        dataset_terms = [
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
        
        # Create dataset mapping and analyze papers
        self.create_dataset_mapping(dataset_terms)
        all_stats, all_paper_data = self.analyze_papers_across_years(bioc_dicts, years)
        
        # Save results
        processed_filepath = self.save_results(all_stats, all_paper_data, bioc_dicts)
        
        end_time = time.time()
        print(f"Total execution time: {end_time - start_time:.2f} seconds")
        return processed_filepath