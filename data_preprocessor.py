"""
Batch Data Preprocessing Script
Cleans all JSON and XLSX files in a directory

Usage:
    python batch_preprocessor.py --input-dir raw_data --output-dir cleaned_data
    python batch_preprocessor.py --input-dir raw_data --output-dir cleaned_data --format json
"""

import json
import pandas as pd
import re
import argparse
from pathlib import Path
from typing import List, Dict
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataPreprocessor:
    """Clean and preprocess data for KG extraction"""
    
    def __init__(self):
        self.stats = {
            'total_records': 0,
            'cleaned_records': 0,
            'removed_records': 0,
            'empty_records': 0,
            'duplicate_records': 0
        }
    
    def reset_stats(self):
        """Reset statistics for new file"""
        self.stats = {
            'total_records': 0,
            'cleaned_records': 0,
            'removed_records': 0,
            'empty_records': 0,
            'duplicate_records': 0
        }
    
    def clean_text(self, text: str) -> str:
        """Clean individual text field"""
        if not text or pd.isna(text):
            return ""
        
        text = str(text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?;:()\-\'\"]+', ' ', text)
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)
        
        # Remove extra spaces again
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def is_valid_record(self, text: str, min_length: int = 10, max_length: int = 50000) -> bool:
        """Check if text record is valid"""
        if not text or len(text.strip()) < min_length:
            return False
        
        if len(text) > max_length:
            logger.warning(f"Text too long ({len(text)} chars), truncating...")
            return True
        
        # Check if text is mostly garbage (too many special chars)
        alpha_ratio = sum(c.isalpha() for c in text) / len(text) if text else 0
        if alpha_ratio < 0.3:
            return False
        
        return True
    
    def preprocess_json(self, filepath: str, text_fields: List[str] = None) -> List[Dict]:
        """Preprocess JSON file"""
        logger.info(f"Processing JSON: {filepath}")
        self.reset_stats()
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            data = [data]
        
        self.stats['total_records'] = len(data)
        
        # Auto-detect text fields
        if not text_fields and len(data) > 0:
            text_fields = self._detect_text_fields(data[0])
        
        cleaned_records = []
        seen_texts = set()
        
        for idx, record in enumerate(data):
            text_parts = []
            
            if text_fields:
                for field in text_fields:
                    if field in record and record[field]:
                        text_parts.append(str(record[field]))
            else:
                for value in record.values():
                    if isinstance(value, str):
                        text_parts.append(value)
            
            combined_text = ' '.join(text_parts)
            cleaned_text = self.clean_text(combined_text)
            
            if not self.is_valid_record(cleaned_text):
                self.stats['empty_records'] += 1
                continue
            
            if cleaned_text in seen_texts:
                self.stats['duplicate_records'] += 1
                continue
            
            seen_texts.add(cleaned_text)
            
            cleaned_record = {
                'id': idx,
                'text': cleaned_text,
                'source': Path(filepath).name
            }
            
            cleaned_records.append(cleaned_record)
            self.stats['cleaned_records'] += 1
        
        self.stats['removed_records'] = self.stats['total_records'] - self.stats['cleaned_records']
        
        return cleaned_records
    
    def preprocess_xlsx(self, filepath: str, text_columns: List[str] = None) -> List[Dict]:
        """Preprocess Excel file"""
        logger.info(f"Processing XLSX: {filepath}")
        self.reset_stats()
        
        df = pd.read_excel(filepath)
        self.stats['total_records'] = len(df)
        
        # Auto-detect text columns
        if not text_columns:
            text_columns = self._detect_text_columns(df)
        
        cleaned_records = []
        seen_texts = set()
        
        for idx, row in df.iterrows():
            text_parts = []
            
            for col in text_columns:
                if col in df.columns and pd.notna(row[col]):
                    text_parts.append(str(row[col]))
            
            combined_text = ' '.join(text_parts)
            cleaned_text = self.clean_text(combined_text)
            
            if not self.is_valid_record(cleaned_text):
                self.stats['empty_records'] += 1
                continue
            
            if cleaned_text in seen_texts:
                self.stats['duplicate_records'] += 1
                continue
            
            seen_texts.add(cleaned_text)
            
            cleaned_record = {
                'id': idx,
                'text': cleaned_text,
                'source': Path(filepath).name,
                'row_number': idx
            }
            
            cleaned_records.append(cleaned_record)
            self.stats['cleaned_records'] += 1
        
        self.stats['removed_records'] = self.stats['total_records'] - self.stats['cleaned_records']
        
        return cleaned_records
    
    def _detect_text_fields(self, sample_record: Dict) -> List[str]:
        """Auto-detect text fields in JSON"""
        text_fields = []
        
        for key, value in sample_record.items():
            if isinstance(value, str):
                key_lower = key.lower()
                if any(keyword in key_lower for keyword in 
                      ['text', 'content', 'body', 'message', 'description', 'summary']):
                    text_fields.append(key)
                elif len(value) > 50:
                    text_fields.append(key)
        
        if not text_fields:
            text_fields = [k for k, v in sample_record.items() if isinstance(v, str)]
        
        return text_fields
    
    def _detect_text_columns(self, df: pd.DataFrame) -> List[str]:
        """Auto-detect text columns in DataFrame"""
        text_columns = []
        
        for col in df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in 
                  ['text', 'content', 'body', 'message', 'description', 'summary']):
                text_columns.append(col)
            elif df[col].dtype == 'object':
                sample = df[col].dropna().head(5)
                if len(sample) > 0:
                    avg_length = sample.astype(str).str.len().mean()
                    if avg_length > 50:
                        text_columns.append(col)
        
        if not text_columns:
            text_columns = [col for col in df.columns if df[col].dtype == 'object']
        
        return text_columns
    
    def save_cleaned_data(self, records: List[Dict], output_path: str):
        """Save cleaned data to JSON"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(records)} records to {output_path}")
    
    def print_file_stats(self, filename: str):
        """Print statistics for a single file"""
        print(f"\n  {filename}:")
        print(f"    Total: {self.stats['total_records']:,} | Cleaned: {self.stats['cleaned_records']:,} | " +
              f"Removed: {self.stats['removed_records']:,} (Empty: {self.stats['empty_records']:,}, Dups: {self.stats['duplicate_records']:,})")


def batch_process(input_dir: str, output_dir: str, file_format: str = 'all'):
    """Process all files in input directory"""
    
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    if not input_path.exists():
        logger.error(f"Input directory not found: {input_dir}")
        return
    
    output_path.mkdir(parents=True, exist_ok=True)
    
    preprocessor = DataPreprocessor()
    
    # Collect files
    json_files = list(input_path.glob('*.json')) if file_format in ['all', 'json'] else []
    xlsx_files = list(input_path.glob('*.xlsx')) + list(input_path.glob('*.xls')) if file_format in ['all', 'xlsx'] else []
    
    total_files = len(json_files) + len(xlsx_files)
    
    if total_files == 0:
        logger.warning(f"No files found in {input_dir}")
        return
    
    print("=" * 60)
    print("BATCH PREPROCESSING")
    print("=" * 60)
    print(f"Input directory:  {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Files to process: {total_files} ({len(json_files)} JSON, {len(xlsx_files)} XLSX)")
    
    total_stats = {
        'files_processed': 0,
        'total_records': 0,
        'cleaned_records': 0
    }
    
    # Process JSON files
    if json_files:
        print(f"\nProcessing JSON files:")
        for json_file in json_files:
            cleaned_records = preprocessor.preprocess_json(str(json_file))
            
            # Create output filename
            output_file = output_path / f"cleaned_{json_file.stem}.json"
            preprocessor.save_cleaned_data(cleaned_records, str(output_file))
            
            preprocessor.print_file_stats(json_file.name)
            
            total_stats['files_processed'] += 1
            total_stats['total_records'] += preprocessor.stats['total_records']
            total_stats['cleaned_records'] += preprocessor.stats['cleaned_records']
    
    # Process XLSX files
    if xlsx_files:
        print(f"\nProcessing XLSX files:")
        for xlsx_file in xlsx_files:
            cleaned_records = preprocessor.preprocess_xlsx(str(xlsx_file))
            
            # Create output filename
            output_file = output_path / f"cleaned_{xlsx_file.stem}.json"
            preprocessor.save_cleaned_data(cleaned_records, str(output_file))
            
            preprocessor.print_file_stats(xlsx_file.name)
            
            total_stats['files_processed'] += 1
            total_stats['total_records'] += preprocessor.stats['total_records']
            total_stats['cleaned_records'] += preprocessor.stats['cleaned_records']
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Files processed:     {total_stats['files_processed']}")
    print(f"Total records:       {total_stats['total_records']:,}")
    print(f"Cleaned records:     {total_stats['cleaned_records']:,}")
    print(f"Retention rate:      {(total_stats['cleaned_records']/total_stats['total_records']*100):.1f}%")
    print(f"\nOutput location:     {output_dir}")
    print(f"\nNext step: Copy cleaned files to your KG pipeline input directory")


def main():
    parser = argparse.ArgumentParser(description='Batch preprocess data files')
    parser.add_argument('--input-dir', required=True, help='Input directory with raw files')
    parser.add_argument('--output-dir', required=True, help='Output directory for cleaned files')
    parser.add_argument('--format', choices=['all', 'json', 'xlsx'], default='all',
                       help='File format to process (default: all)')
    
    args = parser.parse_args()
    
    batch_process(args.input_dir, args.output_dir, args.format)


if __name__ == "__main__":
    main()