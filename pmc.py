# Extracting PMC Papers
from src.pubmed.pmc_scrape import PubMedProcessor
from src.pubmed.query_pmid import query_pmids
from src.pubmed.medline import query_affiliation
def main():

    # Retrieve PMIDs
    pmids, filename = query_pmids()
    """
    Main function to process both PubMed venues.
    Can be modified to process just one venue if needed.
    """
    # Process PubMed papers
    try:
        print("Starting PubMed processing...")
        pubmed_processor = PubMedProcessor(venue="pubmed")
        processed_path = pubmed_processor.process_venue(n=10000, filename=filename)
        print("Basic PubMed processing completed successfully!")
        # Query affiliations
        query_affiliation(processed_path)
        print(f"Affiliation query completed successfully, saved at {processed_path}!")
    except Exception as e:
        print(f"Error processing PubMed papers: {str(e)}")

    # Process AMIA papers (commented out, uncomment if needed)
    """
    try:
        print("\nStarting AMIA processing...")
        amia_processor = PubMedProcessor(venue="amia")
        amia_processor.process_venue(n=10000)
        print("AMIA processing completed successfully!")
    except Exception as e:
        print(f"Error processing AMIA papers: {str(e)}")
    """

    

if __name__ == "__main__":
    main()