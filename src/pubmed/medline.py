from Bio import Medline
import urllib.request as urllib
import pandas as pd
import time
from urllib.error import HTTPError

def get_data(element, source):
    """Get data from source and join if it's a list."""
    value = source.get(element, "")
    if isinstance(value, list):
        value = '||'.join(value)
    return value

def get_author_affiliation(pmid, api_key):
    MEDLINE_URL = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&api_key={api_key}&rettype=medline&retmode=text&id={pmid}"
    text_path = f'medline/pubmed_data_{pmid}.txt'
    try:
        urllib.urlretrieve(MEDLINE_URL, text_path)
        with open(text_path, mode="r", encoding="utf-8") as handle:
            articles = Medline.parse(handle)
            for article in articles:
                return get_data("AD", article)
    except HTTPError as e:
        print(f"HTTP Error occurred for PMID {pmid}: {e}")
        return None
    except Exception as e:
        print(f"An error occurred for PMID {pmid}: {e}")
        return None
    return None  # Return None if no affiliation found

# Function to get affiliation with rate limiting
def get_affiliation_with_rate_limit(row, api_key):
    if row['venue'] == 'pubmed':
        try:
            pmid = str(int(float(row['paper_id'])))  # Convert to int then string to remove any decimal places
            print(f"Processing PMID: {pmid}")
            affiliation = get_author_affiliation(pmid, api_key)
            print(affiliation)
            print(affiliation == None or affiliation == '')
            time.sleep(1.0)  # Sleep for 0.34 seconds to respect rate limit (300 requests per minute)
            return affiliation if affiliation is not None else ''
        except ValueError:
            print(f"Invalid PMID format for paper_id: {row['paper_id']}")
    return ''


def query_affiliation(path, api_key="your_api_key_here"):
    # Load the data
    code = pd.read_csv(path)
    # Add a new 'affiliation' column, initially filled with empty strings
    code['affiliation'] = ''
    # Apply the function to each row
    code['affiliation'] = code.apply(lambda row: get_affiliation_with_rate_limit(row, api_key), axis=1)
    # Save the updated dataframe in place
    code.to_csv(path, index=False)
    print(f"Processing complete. Updated data saved to '{path}'")
    return path


if __name__ == "__main__":
    # for pubmed data
    api_key = "your_api_key_here"
    # Load the data
    code = pd.read_csv("processed_data/combined_data.csv")

    # Add a new 'affiliation' column, initially filled with empty strings
    code['affiliation'] = ''


    # Apply the function to each row
    code['affiliation'] = code.apply(lambda row: get_affiliation_with_rate_limit(row, api_key), axis=1)

    # Save the updated dataframe
    code.to_csv("processed_data/combined_data_medline.csv", index=False)

    print("Processing complete. Updated data saved to 'processed_data/combined_data_medline.csv'")