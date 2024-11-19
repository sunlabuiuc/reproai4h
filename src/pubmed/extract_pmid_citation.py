import pandas as pd 
import pickle 
import csv
import json
import pmidcite
from pmidcite.icite.downloader import get_downloader
from pmc_scrape import load_from_pickle

print(f"pmidcite version: {pmidcite.__version__}")
dnldr = get_downloader()

def get_citation_count(pmid):
    nih_entry = dnldr.get_icite(pmid)
    nih_dict = nih_entry.get_dict()
    return nih_dict["citation_count"]

def get_papers_year(dictionary, year):
    papers = {}
    for pmid, record in dictionary.items():
        if record["year"] == year:
            papers[pmid] = record 
    return papers 

def count_mentions(text, terms):
    if text is None:
        return 0
    text = text.lower()
    return sum(1 for term in terms if term.lower() in text)

def create_dataset_mapping(dataset_terms):
    mapping = {}
    for term_group in dataset_terms:
        key = term_group[0].lower().replace(' ', '_')
        mapping[key] = [term.lower() for term in term_group]
    return mapping

def count_mentions_grouped(text, dataset_mapping):
    if text is None:
        return {}
    text = text.lower()
    counts = {key: 0 for key in dataset_mapping}
    for key, terms in dataset_mapping.items():
        counts[key] = sum(1 for term in terms if term in text)
    return counts

def get_counts_per_paper(year_papers, dataset_mapping):
    counts = {}
    for pmid, record in year_papers.items():
        text = record["content"]
        counts[pmid] = {}
        code_terms = ["github", "gitlab", "zenodo", "colab"]
        dataset_counts = count_mentions_grouped(text, dataset_mapping)
        counts[pmid].update(dataset_counts)
        counts[pmid]["big_datasets"] = sum(dataset_counts.values())
        counts[pmid]["code"] = count_mentions(text, code_terms)
        counts[pmid]["ai"] = count_mentions(text, ["AI", "Artificial Intelligence", "Machine Learning", "Deep Learning", "Neural Network"])
        counts[pmid]["citation_count"] = get_citation_count(pmid)
    print(counts[pmid])
    return counts

def get_analysis(counts, dataset_mapping):
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
    
    for key in dataset_mapping.keys():
        stats[f'files_with_{key}'] = sum(1 for r in counts.values() if r[key] > 0)
        stats[f'total_{key}_mentions'] = sum(r[key] for r in counts.values())
    
    return stats

def get_papers_across_years(dictionary, years, dataset_mapping):
    all_stats = {}
    all_paper_data = {}
    for year in years:
        papers = get_papers_year(dictionary, year)
        counts_each_paper = get_counts_per_paper(papers, dataset_mapping)
        analysis = get_analysis(counts_each_paper, dataset_mapping)
        all_stats[year] = analysis 
        all_paper_data[year] = counts_each_paper

        print(f"Year: {year}, Papers: {len(papers)}")
        print(analysis)
    return all_stats, all_paper_data

def write_stats_to_csv(all_stats, dataset_mapping, filename):
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

def save_paper_data(all_paper_data, json_filename, pkl_filename):
    with open(json_filename, 'w') as f:
        json.dump(all_paper_data, f, indent=4)
    
    with open(pkl_filename, 'wb') as f:
        pickle.dump(all_paper_data, f)

def main():
    bioc_dicts = load_from_pickle("pubmed_content/paper_content_flattened.pkl")
    print(len(bioc_dicts))
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
    
    dataset_mapping = create_dataset_mapping(dataset_terms)
    all_stats, all_paper_data = get_papers_across_years(bioc_dicts, years, dataset_mapping)
    
    # Write stats to CSV
    write_stats_to_csv(all_stats, dataset_mapping, "processed_data/pubmed_stats.csv")
    
    # Save paper data to JSON and PKL
    save_paper_data(all_paper_data, "processed_data/pubmed_paper_data.json", "processed_data/pubmed_paper_data.pkl")

main()