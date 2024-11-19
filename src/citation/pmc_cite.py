import pandas as pd 
import pickle 
import csv
import json
import pmidcite
from pmidcite.icite.downloader import get_downloader
from typing import Dict, List, Any

class PubMedAnalyzer:
    def __init__(self):
        """Initialize the PubMed analyzer with citation downloader."""
        print(f"pmidcite version: {pmidcite.__version__}")
        self.dnldr = get_downloader()
        self.dataset_mapping = {}
    
    def get_citation_count(self, pmid: str) -> int:
        """Get citation count for a given PMID."""
        nih_entry = self.dnldr.get_icite(pmid)
        nih_dict = nih_entry.get_dict()
        return nih_dict["citation_count"]
    
    def get_papers_year(self, dictionary: Dict, year: str) -> Dict:
        """Filter papers by year."""
        return {
            pmid: record for pmid, record in dictionary.items()
            if record["year"] == year
        }
    
    @staticmethod
    def count_mentions(text: str, terms: List[str]) -> int:
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
    
    def count_mentions_grouped(self, text: str) -> Dict:
        """Count mentions of grouped terms in text."""
        if text is None:
            return {key: 0 for key in self.dataset_mapping}
        text = text.lower()
        counts = {key: 0 for key in self.dataset_mapping}
        for key, terms in self.dataset_mapping.items():
            counts[key] = sum(1 for term in terms if term in text)
        return counts
    
    def get_counts_per_paper(self, year_papers: Dict) -> Dict:
        """Get counts of various metrics per paper."""
        counts = {}
        for pmid, record in year_papers.items():
            text = record["content"]
            counts[pmid] = {}
            
            # Count different types of mentions
            code_terms = ["github", "gitlab", "zenodo", "colab"]
            dataset_counts = self.count_mentions_grouped(text)
            counts[pmid].update(dataset_counts)
            counts[pmid]["big_datasets"] = sum(dataset_counts.values())
            counts[pmid]["code"] = self.count_mentions(text, code_terms)
            counts[pmid]["ai"] = self.count_mentions(text, [
                "AI", "Artificial Intelligence", "Machine Learning", 
                "Deep Learning", "Neural Network"
            ])
            counts[pmid]["citation_count"] = self.get_citation_count(pmid)
            
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
        
        for key in self.dataset_mapping.keys():
            stats[f'files_with_{key}'] = sum(1 for r in counts.values() if r[key] > 0)
            stats[f'total_{key}_mentions'] = sum(r[key] for r in counts.values())
        
        return stats
    
    def analyze_papers_across_years(self, dictionary: Dict, years: List[str]) -> tuple:
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
    
    @staticmethod
    def write_stats_to_csv(all_stats: Dict, dataset_mapping: Dict, filename: str):
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
            
            for key in dataset_mapping.keys():
                stats_keys.extend([f'files_with_{key}', f'total_{key}_mentions'])
            
            for key in stats_keys:
                row = [key.replace('_', ' ').title()]
                for year in all_stats.keys():
                    row.append(all_stats[year].get(key, ''))
                writer.writerow(row)
    
    @staticmethod
    def save_paper_data(all_paper_data: Dict, json_filename: str, pkl_filename: str):
        """Save paper data to JSON and pickle files."""
        with open(json_filename, 'w') as f:
            json.dump(all_paper_data, f, indent=4)
        
        with open(pkl_filename, 'wb') as f:
            pickle.dump(all_paper_data, f)