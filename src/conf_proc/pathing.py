from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from pathlib import Path
import random
import shutil

@dataclass
class ConferenceConfig:
    name: str
    years: List[int]
    base_urls: List[str]
    folder_prefix: str
    debug_year: int = field(default=2023)  # Default year for debug mode
    debug_paper_count: int = field(default=5)  # Number of papers to use in debug mode
    debug_papers: Set[str] = field(default_factory=set)  # Track which papers are included in debug

    def get_years(self, debug: bool = False) -> List[int]:
        """Get relevant years based on mode"""
        if debug:
            return [self.debug_year]
        return self.years

    def get_urls(self, debug: bool = False) -> List[str]:
        """Get relevant URLs based on mode"""
        if debug:
            # Find the URL corresponding to the debug year
            year_index = self.years.index(self.debug_year)
            return [self.base_urls[year_index]]
        return self.base_urls
    
class ConferencePathManager:
    """Centralized path management for conference paper processing with debug mode"""
    
    def __init__(self, base_dir: str = "data", debug: bool = False):
        self.debug = debug
        self.base_dir = Path(base_dir)
        if debug:
            self.base_dir = self.base_dir / "debug"
            
        self.conference_configs = {
            'ml4h': ConferenceConfig(
                name="ML4H",
                years=[2019, 2020, 2021, 2022, 2023],
                base_urls=[
                    "https://proceedings.mlr.press/v116/",
                    "https://proceedings.mlr.press/v136/",
                    "https://proceedings.mlr.press/v158/",
                    "https://proceedings.mlr.press/v193/",
                    "https://proceedings.mlr.press/v225/"
                ],
                folder_prefix="ml4h",
                debug_year=2023,
                debug_paper_count=5
            ),
            'chil': ConferenceConfig(
                name="CHIL",
                years=[2020, 2021, 2022, 2023, 2024],
                base_urls=[
                    "https://proceedings.mlr.press/v174/",
                    "https://proceedings.mlr.press/v209/",
                    "https://proceedings.mlr.press/v248/"
                ],
                folder_prefix="chil"
            ),
            'mlhc': ConferenceConfig(
                name="MLHC",
                years=[2017, 2018, 2019, 2020, 2021, 2022, 2023],
                base_urls=[
                    "https://www.mlforhc.org/2018",
                    "https://www.mlforhc.org/2019-conference",
                    "https://www.mlforhc.org/2020accepted-papers",
                    "https://www.mlforhc.org/2021-accepted-papers",
                    "https://www.mlforhc.org/2022-accepted-papers",
                    "https://www.mlforhc.org/2023-accepted-papers"
                ],
                folder_prefix="mlhc"
            )
        }

    def setup_debug_environment(self, conference: str = 'ml4h'):
        """Set up a debug environment with a small subset of papers"""
        if not self.debug:
            return

        conf = self.get_conference_config(conference)
        source_paths = self.get_paths(conference, conf.debug_year, debug=False)
        debug_paths = self.get_paths(conference, conf.debug_year, debug=True)

        # Clean any existing debug directory
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)

        # Create debug directories
        for path in debug_paths.values():
            path.mkdir(parents=True, exist_ok=True)

        # Copy a random subset of PDFs if they exist
        if source_paths['year_pdfs'].exists():
            pdf_files = list(source_paths['year_pdfs'].glob('*.pdf'))
            if pdf_files:
                selected_pdfs = random.sample(
                    pdf_files, 
                    min(len(pdf_files), conf.debug_paper_count)
                )
                for pdf in selected_pdfs:
                    shutil.copy2(pdf, debug_paths['year_pdfs'])
                    conf.debug_papers.add(pdf.name)
                print(f"Debug mode: Selected {len(selected_pdfs)} papers from {conf.debug_year}")
                for pdf in selected_pdfs:
                    print(f"- {pdf.name}")

    def get_conference_config(self, conference: str) -> ConferenceConfig:
        """Get configuration for a specific conference"""
        return self.conference_configs[conference.lower()]

    def get_paths(self, conference: str, year: Optional[int] = None, debug: Optional[bool] = None) -> Dict[str, Path]:
        """Get all relevant paths for a conference and optionally a specific year"""
        if debug is None:
            debug = self.debug
            
        conf = self.get_conference_config(conference)
        base = Path("data/debug" if debug else "data")
        
        paths = {
            'raw_pdfs': base / 'raw' / conf.folder_prefix / 'pdf',
            'processed': base / 'processed' / conf.folder_prefix,
            'cleaned': base / 'cleaned' / conf.folder_prefix,
            'extracted': base / 'extracted' / conf.folder_prefix,
        }
        
        if year:
            paths.update({
                'year_pdfs': base / 'raw' / conf.folder_prefix / f"{year}pdf",
                'year_processed': paths['processed'] / str(year),
                'year_cleaned': paths['cleaned'] / str(year),
                'year_extracted': paths['extracted'] / str(year),
            })
        
        # Create all directories
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
            
        return paths

    def get_output_filename(self, conference: str, year: Optional[int] = None, 
                          stage: str = 'processed') -> Path:
        """Generate consistent output filename for different processing stages"""
        conf = self.get_conference_config(conference)
        paths = self.get_paths(conference)
        
        if year:
            base_name = f"{conf.folder_prefix}_{year}_{stage}.csv"
        else:
            base_name = f"{conf.folder_prefix}_{stage}.csv"
            
        return paths[stage] / base_name

    def should_process_file(self, filename: str, conference: str) -> bool:
        """Check if a file should be processed in debug mode"""
        if not self.debug:
            return True
        return filename in self.conference_configs[conference].debug_papers

# Example usage in main script:
# def main():
#     # Initialize path manager in debug mode
#     path_manager = ConferencePathManager(base_dir="data", debug=True)
    
#     # Set up debug environment with 5 random papers from ML4H 2023
#     path_manager.setup_debug_environment(conference='ml4h')
    
#     # Initialize processors with debug path manager
#     downloader = ConferenceDownloader(path_manager)
#     processor = PDFContentProcessor(path_manager)
#     cleaner = ConferencePaperCleaner(path_manager, device="cuda:0")
    
#     # Process only ML4H in debug mode
#     conference = 'ml4h'
#     print(f"\nProcessing {conference.upper()} in debug mode...")
#     downloader.process_conference(conference)
#     processor.process_conference(conference)
#     cleaner.clean_conference_papers(conference)

# if __name__ == "__main__":
#     main()