import pandas as pd
import requests
from urllib.parse import quote
import re
import time

def word_overlap(str1, str2):
    words1 = re.findall(r'\w+', str1.lower())
    words2 = re.findall(r'\w+', str2.lower())
    overlap = sum(any(w2.startswith(w1) or w1.startswith(w2) for w2 in words2) for w1 in words1)
    return overlap

def find_paper_datasets(search_title):
    base_url = "https://paperswithcode.com/api/v1/papers/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        search_url = f"{base_url}?title={quote(search_title)}"
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()
        search_data = response.json()

        for paper in search_data.get('results', []):
            overlap = word_overlap(search_title, paper['title'])
            if overlap >= 3:
                paper_id = paper['id']
                datasets_url = f"{base_url}{paper_id}/datasets/"
                dataset_response = requests.get(datasets_url, headers=headers)
                dataset_response.raise_for_status()
                dataset_data = dataset_response.json()
                return len(dataset_data.get('results', []))

        return 0

    except requests.RequestException as e:
        print(f"An error occurred for title '{search_title}': {e}")
        return 0

def update_dataframe_with_dataset_count(df):
    df['paper_with_code_data_count'] = 0
    total_rows = len(df)

    for index, row in df.iterrows():
        if index % 10 == 0:
            print(f"Processing row {index+1}/{total_rows}")

        search_title = row['cleaned_title'] if pd.notna(row['cleaned_title']) and row['cleaned_title'] != '' else row['title']
        
        if pd.isna(search_title) or search_title == '':
            continue

        dataset_count = find_paper_datasets(search_title)
        df.at[index, 'paper_with_code_data_count'] = dataset_count

        # time.sleep(0.5)  # 0.5 second delay between API calls

    return df

# Load your DataFrame

def papers_with_code(path):
    topic_df = pd.read_csv(path)
    print(f"Original DataFrame length: {len(topic_df)}")

    # Update the DataFrame with dataset counts
    updated_df = update_dataframe_with_dataset_count(topic_df)

    # Save the updated DataFrame
    updated_df.to_csv("data/final_processed.csv", index=False)
    print(f"Updated DataFrame saved. New column added: paper_with_code_data_count")
    print(f"Final DataFrame length: {len(updated_df)}")