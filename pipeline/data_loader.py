"""
Minimal data loader - handles all common file types automatically
"""

import json
import csv
import os
from pathlib import Path
import pandas as pd

# Optional imports
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class DataLoader:
    """Simple loader for all file types"""
    
    def load_all_from_directory(self, directory_path):
        """Load all supported files from directory"""
        
        directory = Path(directory_path)
        if not directory.exists():
            print(f"Directory not found: {directory_path}")
            return []
        
        all_text_blocks = []
        
        for file_path in directory.iterdir():
            if file_path.is_file():
                try:
                    blocks = self.load_file(str(file_path))
                    all_text_blocks.extend(blocks)
                    print(f"✓ {file_path.name}: {len(blocks)} text blocks")
                except Exception as e:
                    print(f"✗ {file_path.name}: {str(e)}")
        
        print(f"\nTotal: {len(all_text_blocks)} text blocks loaded")
        return all_text_blocks
    
    def load_file(self, file_path):
        """Auto-detect file type and load"""
        
        extension = Path(file_path).suffix.lower()
        
        if extension == '.json':
            return self._load_json(file_path)
        elif extension == '.csv':
            return self._load_csv(file_path)
        elif extension == '.txt':
            return self._load_txt(file_path)
        elif extension == '.pdf' and PDF_AVAILABLE:
            return self._load_pdf(file_path)
        elif extension in ['.docx', '.doc'] and DOCX_AVAILABLE:
            return self._load_docx(file_path)
        else:
            return self._load_as_text(file_path)  # Fallback for any text file
    
    def _load_json(self, file_path):
        """Load JSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        blocks = []
        if isinstance(data, list):
            for i, item in enumerate(data):
                text = self._extract_text(item)
                if len(text.strip()) > 10:
                    blocks.append({
                        'text': text,
                        'source': Path(file_path).name,
                        'block_id': f"json_{i}"
                    })
        else:
            text = self._extract_text(data)
            if len(text.strip()) > 10:
                blocks.append({
                    'text': text,
                    'source': Path(file_path).name,
                    'block_id': "json_0"
                })
        
        return blocks
    
    def _load_csv(self, file_path):
        """Load CSV file"""
        df = pd.read_csv(file_path)
        
        # Find text columns
        text_cols = []
        for col in df.columns:
            if any(word in col.lower() for word in ['text', 'content', 'body', 'message', 'description']):
                text_cols.append(col)
        
        if not text_cols:
            text_cols = [col for col in df.columns if df[col].dtype == 'object']
        
        blocks = []
        for i, row in df.iterrows():
            text_parts = []
            for col in text_cols:
                if pd.notna(row[col]):
                    text_parts.append(str(row[col]))
            
            text = ' '.join(text_parts)
            if len(text.strip()) > 10:
                blocks.append({
                    'text': text,
                    'source': Path(file_path).name,
                    'block_id': f"csv_{i}"
                })
        
        return blocks
    
    def _load_txt(self, file_path):
        """Load text file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 10]
        
        blocks = []
        for i, paragraph in enumerate(paragraphs):
            blocks.append({
                'text': paragraph,
                'source': Path(file_path).name,
                'block_id': f"txt_{i}"
            })
        
        return blocks
    
    def _load_pdf(self, file_path):
        """Load PDF file"""
        blocks = []
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if len(text.strip()) > 10:
                    blocks.append({
                        'text': text,
                        'source': Path(file_path).name,
                        'block_id': f"pdf_{i}"
                    })
        return blocks
    
    def _load_docx(self, file_path):
        """Load DOCX file"""
        doc = Document(file_path)
        blocks = []
        
        for i, paragraph in enumerate(doc.paragraphs):
            text = paragraph.text.strip()
            if len(text) > 10:
                blocks.append({
                    'text': text,
                    'source': Path(file_path).name,
                    'block_id': f"docx_{i}"
                })
        
        return blocks
    
    def _load_as_text(self, file_path):
        """Fallback - try to load any file as text"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if len(content.strip()) > 10:
                return [{
                    'text': content,
                    'source': Path(file_path).name,
                    'block_id': "text_0"
                }]
        except:
            pass
        
        return []
    
    def _extract_text(self, item):
        """Extract text from various formats"""
        if isinstance(item, str):
            return item
        elif isinstance(item, dict):
            # Try common text fields
            for field in ['text', 'content', 'body', 'message', 'description']:
                if field in item and item[field]:
                    return str(item[field])
            # Concatenate all string values
            return ' '.join(str(v) for v in item.values() if isinstance(v, str))
        else:
            return str(item)