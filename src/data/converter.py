"""
Data Converter Module
Converts all ingested data blocks into standardized JSON format
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DataConverter:
    """
    Converts data blocks from various sources into standardized JSON format
    for knowledge graph extraction
    """

    def __init__(self, config: Dict = None):
        """
        Initialize DataConverter

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = logger

    def convert_to_json(self, blocks: List[Dict[str, Any]], output_path: str) -> str:
        """
        Convert data blocks to standardized JSON format

        Args:
            blocks: List of text blocks with metadata
            output_path: Directory to save JSON file

        Returns:
            Path to the created JSON file
        """
        if not blocks:
            self.logger.warning("No blocks to convert")
            return None

        # Create standardized structure
        standardized_data = {
            'metadata': {
                'total_blocks': len(blocks),
                'conversion_timestamp': datetime.now().isoformat(),
                'source_types': self._get_source_types(blocks),
                'source_files': self._get_source_files(blocks)
            },
            'blocks': []
        }

        # Convert each block to standardized format
        for idx, block in enumerate(blocks):
            standardized_block = {
                'block_id': f"block_{idx}",
                'text': block.get('text', ''),
                'source': {
                    'file': block.get('source_file', 'unknown'),
                    'type': block.get('source_type', 'unknown'),
                    'index': block.get('index', idx)
                },
                'metadata': block.get('metadata', {}),
                'stats': {
                    'char_count': len(block.get('text', '')),
                    'word_count': len(block.get('text', '').split())
                }
            }
            standardized_data['blocks'].append(standardized_block)

        # Save to file
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"converted_data_{timestamp}.json"
        filepath = output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(standardized_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Converted {len(blocks)} blocks to {filepath}")
        return str(filepath)

    def convert_batch_to_json(self, blocks: List[Dict[str, Any]], output_path: str, batch_size: int = 1000) -> List[str]:
        """
        Convert large datasets in batches

        Args:
            blocks: List of text blocks
            output_path: Directory to save JSON files
            batch_size: Number of blocks per file

        Returns:
            List of created file paths
        """
        if not blocks:
            self.logger.warning("No blocks to convert")
            return []

        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        created_files = []
        total_batches = (len(blocks) + batch_size - 1) // batch_size

        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(blocks))
            batch = blocks[start_idx:end_idx]

            # Create batch data structure
            batch_data = {
                'metadata': {
                    'batch_index': batch_idx,
                    'batch_size': len(batch),
                    'start_index': start_idx,
                    'end_index': end_idx,
                    'total_blocks': len(blocks),
                    'conversion_timestamp': datetime.now().isoformat()
                },
                'blocks': []
            }

            # Convert blocks in batch
            for local_idx, block in enumerate(batch):
                global_idx = start_idx + local_idx
                standardized_block = {
                    'block_id': f"block_{global_idx}",
                    'text': block.get('text', ''),
                    'source': {
                        'file': block.get('source_file', 'unknown'),
                        'type': block.get('source_type', 'unknown'),
                        'index': block.get('index', local_idx)
                    },
                    'metadata': block.get('metadata', {}),
                    'stats': {
                        'char_count': len(block.get('text', '')),
                        'word_count': len(block.get('text', '').split())
                    }
                }
                batch_data['blocks'].append(standardized_block)

            # Save batch file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"converted_batch_{batch_idx}_{timestamp}.json"
            filepath = output_dir / filename

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(batch_data, f, indent=2, ensure_ascii=False)

            created_files.append(str(filepath))
            self.logger.info(f"Created batch file {batch_idx + 1}/{total_batches}: {filepath}")

        self.logger.info(f"Converted {len(blocks)} blocks to {len(created_files)} batch files")
        return created_files

    def load_converted_json(self, json_path: str) -> List[Dict[str, Any]]:
        """
        Load previously converted JSON file

        Args:
            json_path: Path to JSON file

        Returns:
            List of text blocks
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        blocks = data.get('blocks', [])
        self.logger.info(f"Loaded {len(blocks)} blocks from {json_path}")
        return blocks

    def load_all_converted_json(self, directory_path: str) -> List[Dict[str, Any]]:
        """
        Load all converted JSON files from a directory

        Args:
            directory_path: Directory containing converted JSON files

        Returns:
            Combined list of all text blocks
        """
        directory = Path(directory_path)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")

        all_blocks = []
        json_files = sorted(directory.glob("converted_*.json"))

        for json_file in json_files:
            blocks = self.load_converted_json(str(json_file))
            all_blocks.extend(blocks)

        self.logger.info(f"Loaded {len(all_blocks)} total blocks from {len(json_files)} files")
        return all_blocks

    def _get_source_types(self, blocks: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get count of blocks by source type"""
        source_types = {}
        for block in blocks:
            source_type = block.get('source_type', 'unknown')
            source_types[source_type] = source_types.get(source_type, 0) + 1
        return source_types

    def _get_source_files(self, blocks: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get count of blocks by source file"""
        source_files = {}
        for block in blocks:
            source_file = block.get('source_file', 'unknown')
            source_files[source_file] = source_files.get(source_file, 0) + 1
        return source_files

    def merge_json_files(self, input_paths: List[str], output_path: str) -> str:
        """
        Merge multiple JSON files into a single file

        Args:
            input_paths: List of JSON file paths to merge
            output_path: Output file path

        Returns:
            Path to merged file
        """
        all_blocks = []

        for path in input_paths:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                blocks = data.get('blocks', [])
                all_blocks.extend(blocks)

        # Create merged structure
        merged_data = {
            'metadata': {
                'total_blocks': len(all_blocks),
                'source_files_count': len(input_paths),
                'merge_timestamp': datetime.now().isoformat()
            },
            'blocks': all_blocks
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Merged {len(input_paths)} files into {output_file}")
        return str(output_file)
