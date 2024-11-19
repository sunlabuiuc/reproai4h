# Bridging the Reproducibility Divide: Open Source Software's Role in Standardizing Healthcare AI4H

## Overview
This repository contains the reproducibility study conducted for our submitted publication "Bridging the Reproducibility Divide: Open Source Software's Role in Standardizing Healthcare AI4H". We provide a step-by-step guide for those who wish to reproduce our data collection and analysis procedures as outlined in the figure below.

![Pipeline](figures/ScrapingPipeline.drawio(1).png)

## Data
The complete dataset used in our analysis can be found in:
- `data/processed_final.csv`

## Analysis and Visualization
Our figures and numerical analyses are implemented in the following Jupyter notebooks:

1. `plot_general.ipynb`
   - Contains all code for generating Figure 1

2. `plot_code.ipynb`
   - Contains all code for generating Figure 2

3. `plot_data.ipynb`
   - Contains all code for generating Figure 3

## Requirements

### Dependencies
While it is suggested to create a new environment for this project, please follow these steps to set up the environment and install the prerequisite packages:

1. Create a new conda environment named "reproAI4H":
```bash
conda create -n reproAI4H python=3.10
```

2. Activate the environment:
```bash
conda activate reproAI4H
```

3. Install the required packages from requirements.txt:
```bash
pip install -r requirements.txt
```

*Note: Make sure you have Anaconda or Miniconda installed on your system before running these commands.*

### System Requirements
We note that it is crucial that you have enough GPU memory to run open source 70B LLMs for topic classification and conference paper title and author extraction. We ran all of our experiments using a single A6000 GPU with 48GB of VRAM. 

While one can potentially attempt to use smaller 8B or 7B models, their performance is typically poor.

### API's

We note that getting access to each service's API's may not be trivial. For getting access to SemanticScholar API, you will have to apply for it [here](https://www.semanticscholar.org/product/api). For getting access to Medline's API, you will need to get a PubMed API key [here](https://support.nlm.nih.gov/kbArticle/?pn=KA-05317). Finally, SerpAPI can be accessed simply by accessing their website [here](https://serpapi.com/).


## Scraping Conference Papers
One can retrace our steps for scraping conference papers by running

```bash
python3 conf.py 
```

However, please note that you will have to manually download 2 years of the CHIL papers as they were unscrapeable due to them being stored on ACM's website. 

### Retrieving Conference Papers
We share our webscraping code in `src/conf_proc/scrape_conf.py`

### Cleaning PDFs
We share our LLM title and author extraction code in `src/conf_proc/clean_conf.py`.


### Measuring Code Sharing and Public Dataset Usage
All code for code sharing and public dataset usage is in  `src/conf_proc/measure_conf.py`.


### Retrieving Citation Data (Semantic Scholar and SerpAPI)
We note that we primarily use semantic scholar and SerpAPI to retrieve conference paper statistics as PubMed doesn't actively store conference papers. The semantic scholar querying code is in `src/citation/semantic_scholar.py`.

We note that SerpAPI was queried using a free account and is then done through the jupyter notebook `serpapi_conference_papers.ipynb` with their provided API for all the papers missing from the initial semantic scholar check. Please make sure you run this notebook after running the above.

## Scraping PubMed
One can retrace our steps for scraping PubMed papers by running

```bash
python3 pmc.py 
```

### PMID Query
All code for querying PubMed's AI4H papers is in `src/pubmed/query_pmid.py`

### Medline Affiliation Extraction 
We query all medline affiliations using the code defined in `src/pubmed/medline.py`.

### Code Sharing and Public Dataset Usage
All processing and analysis code is defined in `src/pubmed/pmc_scrape.py`

## Combined Analysis
Running our combined analysis such as topic classification and checking with papers with code can be done through 

```bash
python3 combine_classify.py
```

### Papers with Code API Check
We cross-check public dataset usage using papers with code using the code in `src/citation/papers_with_code.py`.

### Topic Classification
We showcase our topic classification code in `src/topic/classification.py`.

## Manual Evaluation Results
We also include manual evaluation results in 
- `data/validation.csv`
  
which can be used to compute the final validation results in the Appendix table using
- `validation.ipynb`


## Contact
Please make a github issue and/or email johnwu3@illinois.edu if something doesn't run properly. I haven't properly debugged this code after cleaning up the mess that I was originally doing as I was originally building the analysis platform.