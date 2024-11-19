import requests
from bs4 import BeautifulSoup
import PyPDF2
import io
from urllib.parse import urljoin, urlparse
import time
import random
import os
from src.conf_proc.pathing import ConferencePathManager

# Modified main classes to use the path manager
class ConferenceDownloader:
    def __init__(self, path_manager: ConferencePathManager):
        self.path_manager = path_manager
        self.session = self._create_session()

    def _create_session(self):
        """Create a session with appropriate headers"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        return session

    def scrape_webpage(self, url):
        """Scrape webpage for PDF links"""
        response = self.session.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            pdf_links = []
            for link in soup.find_all('a'):
                href = link.get('href')
                if href and href.lower().endswith('.pdf'):
                    full_url = urljoin(url, href)
                    pdf_links.append((full_url, link.text))
            return pdf_links
        else:
            print(f"Failed to retrieve the webpage. Status code: {response.status_code}")
            return []

    def download_pdf(self, pdf_url, year_folder, all_folder, max_retries=3, retry_delay=5):
        """Download PDF and save to specified folders"""
        # Create the folders if they don't exist
        for folder in [year_folder, all_folder]:
            if not os.path.exists(folder):
                os.makedirs(folder)

        # Generate a filename from the URL
        filename = os.path.basename(urlparse(pdf_url).path)
        year_filename = os.path.join(year_folder, filename)
        all_filename = os.path.join(all_folder, filename)

        for attempt in range(max_retries):
            response = self.session.get(pdf_url)
            if response.status_code == 200:
                # Save in year-specific folder
                with open(year_filename, 'wb') as f:
                    f.write(response.content)
                # Save in 'all' folder
                with open(all_filename, 'wb') as f:
                    f.write(response.content)
                print(f"Successfully downloaded: {filename}")
                return year_filename
            elif response.status_code == 429:
                print(f"Rate limited. Waiting {retry_delay} seconds before retrying...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print(f"Failed to download the PDF. Status code: {response.status_code}")
                return None

        print(f"Max retries reached for {pdf_url}")
        return None

    def extract_pdf_content(self, filename):
        """Extract text content from PDF file"""
        try:
            with open(filename, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()
                return text
        except Exception as e:
            print(f"Error extracting content from {filename}: {str(e)}")
            return None

    def process_conference(self, conference: str):
        conf = self.path_manager.get_conference_config(conference)
        years = conf.get_years(self.path_manager.debug)
        urls = conf.get_urls(self.path_manager.debug)
        
        for year, base_url in zip(years, urls):
            paths = self.path_manager.get_paths(conference, year)
            pdf_links = self.scrape_webpage(base_url)
            
            # In debug mode, just take the first 5 papers
            if self.path_manager.debug:
                pdf_links = pdf_links[:5]
                print(f"\nDebug mode: Processing first {len(pdf_links)} papers from {year}")
                for url, title in pdf_links:
                    print(f"- {title}")
            
            for pdf_url, pdf_title in pdf_links:
                self.download_pdf(
                    pdf_url, 
                    paths['year_pdfs'],
                    paths['raw_pdfs']
                )
                print(f"Finished downloading {pdf_title}")
                

        print(f"Finished processing {conference.upper()} conference papers.")
        print("==="*20)


    def process_all_conferences(self):
        """Process all configured conferences"""
        for conference in self.conferences:
            self.process_conference(conference)

    def add_conference(self, name, base_urls, years, folder_prefix):
        """Add a new conference configuration"""
        self.conferences[name] = {
            'base_urls': base_urls,
            'years': years,
            'folder_prefix': folder_prefix
        }

    def get_conference_info(self, conference_name):
        """Get configuration for a specific conference"""
        return self.conferences.get(conference_name)

    def list_conferences(self):
        """List all configured conferences"""
        return list(self.conferences.keys())