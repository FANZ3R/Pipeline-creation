"""
Pipeline Orchestrator Module
Main coordinator for the entire knowledge graph extraction pipeline
"""

import logging
import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional
import spacy

from ..data import DataIngestion, DataConverter, DataValidator
from ..extraction import KnowledgeGraphBuilder
from ..storage import FileSaver, Neo4jConnector
from .monitoring import PipelineMonitor

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Main orchestrator for the automated knowledge graph extraction pipeline

    Workflow:
    1. Data Ingestion: Load all formats from raw directory
    2. Data Conversion: Convert to standardized JSON
    3. Data Validation: Clean and validate data
    4. KG Extraction: Extract entities and relationships
    5. Storage: Save to JSON, CSV, and optionally Neo4j
    6. Monitoring: Track progress and generate reports
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize PipelineOrchestrator

        Args:
            config_path: Path to YAML configuration file (default: config/default.yaml)
        """
        # Load configuration
        if config_path is None:
            config_path = "config/default.yaml"

        self.config = self._load_config(config_path)
        self.monitor = PipelineMonitor()
        self.logger = logger

        # Setup logging
        self._setup_logging()

        # Initialize components
        self.nlp = None
        self.data_ingestion = None
        self.data_converter = None
        self.data_validator = None
        self.kg_builder = None
        self.file_saver = None
        self.neo4j_connector = None

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {config_path}")
            return config
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
            logger.info("Using default configuration")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'ingestion': {'min_text_length': 10},
            'validation': {'enabled': True, 'min_quality_score': 0.3},
            'extraction': {'spacy_model': 'en_core_web_sm', 'batch_size': 50},
            'output': {'base_dir': 'data/output', 'formats': ['json', 'csv']},
            'neo4j': {'enabled': False},
            'logging': {'level': 'INFO', 'file': 'logs/pipeline.log'},
            'pipeline': {
                'input_dir': 'data/raw',
                'processed_dir': 'data/processed',
                'output_dir': 'data/output',
                'convert_to_json': True
            }
        }

    def _setup_logging(self):
        """Setup logging configuration"""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO'))
        log_file = log_config.get('file', 'logs/pipeline.log')

        # Create logs directory
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format=log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

    def initialize_components(self):
        """Initialize all pipeline components"""
        self.logger.info("Initializing pipeline components...")

        # Load spaCy model
        model_name = self.config.get('extraction', {}).get('spacy_model', 'en_core_web_sm')
        try:
            self.nlp = spacy.load(model_name)
            self.logger.info(f"Loaded spaCy model: {model_name}")
        except OSError:
            self.logger.error(f"spaCy model '{model_name}' not found. Run: python -m spacy download {model_name}")
            raise

        # Initialize components
        self.data_ingestion = DataIngestion(self.config.get('ingestion', {}))
        self.data_converter = DataConverter(self.config.get('pipeline', {}))
        self.data_validator = DataValidator(self.config.get('validation', {}))
        self.kg_builder = KnowledgeGraphBuilder(self.nlp, self.config.get('extraction', {}))

        # Initialize file saver
        output_dir = self.config.get('pipeline', {}).get('output_dir', 'data/output')
        self.file_saver = FileSaver(output_dir, self.config.get('output', {}))

        # Initialize Neo4j if enabled
        neo4j_config = self.config.get('neo4j', {})
        if neo4j_config.get('enabled', False):
            self.neo4j_connector = Neo4jConnector(
                uri=neo4j_config.get('uri', 'bolt://localhost:7687'),
                username=neo4j_config.get('username', 'neo4j'),
                password=neo4j_config.get('password', 'password'),
                config=neo4j_config
            )

        self.logger.info("All components initialized successfully")

    def run(self):
        """
        Run the complete automated pipeline
        """
        self.monitor.start_pipeline()

        try:
            # Stage 1: Data Ingestion
            self.monitor.start_stage("Data Ingestion")
            raw_blocks = self._run_data_ingestion()
            self.monitor.record_metric("Data Ingestion", "blocks_loaded", len(raw_blocks))
            self.monitor.end_stage("Data Ingestion")

            # Stage 2: Data Conversion (optional)
            if self.config.get('pipeline', {}).get('convert_to_json', True):
                self.monitor.start_stage("Data Conversion")
                self._run_data_conversion(raw_blocks)
                self.monitor.end_stage("Data Conversion")

            # Stage 3: Data Validation
            self.monitor.start_stage("Data Validation")
            validated_blocks = self._run_data_validation(raw_blocks)
            self.monitor.record_metric("Data Validation", "blocks_validated", len(validated_blocks))
            self.monitor.end_stage("Data Validation")

            # Stage 4: Knowledge Graph Extraction
            self.monitor.start_stage("KG Extraction")
            extraction_result = self._run_kg_extraction(validated_blocks)
            self.monitor.record_metric("KG Extraction", "entities_extracted", len(extraction_result['entities']))
            self.monitor.record_metric("KG Extraction", "relationships_extracted", len(extraction_result['relationships']))
            self.monitor.end_stage("KG Extraction")

            # Stage 5: Storage
            self.monitor.start_stage("Storage")
            saved_files = self._run_storage(extraction_result)
            self.monitor.record_metric("Storage", "files_created", len(saved_files))
            self.monitor.end_stage("Storage")

            # Stage 6: Neo4j Export (if enabled)
            if self.neo4j_connector:
                self.monitor.start_stage("Neo4j Export")
                neo4j_stats = self._run_neo4j_export(extraction_result)
                if neo4j_stats:
                    self.monitor.record_metric("Neo4j Export", "nodes_created", neo4j_stats.get('total_nodes', 0))
                    self.monitor.record_metric("Neo4j Export", "relationships_created", neo4j_stats.get('total_relationships', 0))
                self.monitor.end_stage("Neo4j Export")

            self.monitor.end_pipeline()

            # Print summary
            self.monitor.print_summary()

            # Save summary report
            summary_text = self.file_saver.create_summary_report(extraction_result)
            print(summary_text)

            self.logger.info("Pipeline execution completed successfully!")

            return extraction_result

        except Exception as e:
            self.monitor.record_error("Pipeline", str(e))
            self.logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            raise

    def _run_data_ingestion(self):
        """Run data ingestion stage"""
        input_dir = self.config.get('pipeline', {}).get('input_dir', 'data/raw')

        if not Path(input_dir).exists():
            Path(input_dir).mkdir(parents=True, exist_ok=True)
            self.logger.warning(f"Created input directory: {input_dir}")
            self.logger.info(f"Please add your data files to {input_dir} and run again")
            return []

        self.logger.info(f"Loading data from {input_dir}...")
        blocks = self.data_ingestion.load_from_directory(input_dir)

        # Get and log statistics
        stats = self.data_ingestion.get_statistics(blocks)
        self.logger.info(f"Ingestion stats: {stats}")

        return blocks

    def _run_data_conversion(self, blocks):
        """Run data conversion stage"""
        if not blocks:
            self.logger.warning("No blocks to convert")
            return None

        processed_dir = self.config.get('pipeline', {}).get('processed_dir', 'data/processed')
        json_batch_size = self.config.get('pipeline', {}).get('json_batch_size', 1000)

        self.logger.info(f"Converting {len(blocks)} blocks to JSON...")

        if len(blocks) > json_batch_size:
            # Batch conversion for large datasets
            created_files = self.data_converter.convert_batch_to_json(blocks, processed_dir, json_batch_size)
            self.logger.info(f"Created {len(created_files)} JSON batch files")
        else:
            # Single file conversion
            created_file = self.data_converter.convert_to_json(blocks, processed_dir)
            self.logger.info(f"Created JSON file: {created_file}")

        return processed_dir

    def _run_data_validation(self, blocks):
        """Run data validation stage"""
        if not blocks:
            self.logger.warning("No blocks to validate")
            return []

        validation_config = self.config.get('validation', {})

        if not validation_config.get('enabled', True):
            self.logger.info("Validation disabled, skipping...")
            return blocks

        # Validate blocks
        valid_blocks, validation_stats = self.data_validator.validate_blocks(blocks)
        self.logger.info(f"Validation stats: {validation_stats}")

        # Clean blocks
        if validation_config.get('remove_urls', True) or validation_config.get('remove_emails', True):
            valid_blocks = self.data_validator.clean_blocks(valid_blocks)

        # Deduplicate
        if validation_config.get('deduplicate', True):
            valid_blocks = self.data_validator.deduplicate_blocks(valid_blocks)

        # Filter by quality
        min_quality = validation_config.get('min_quality_score', 0.3)
        valid_blocks = self.data_validator.filter_by_quality(valid_blocks, min_quality)

        return valid_blocks

    def _run_kg_extraction(self, blocks):
        """Run knowledge graph extraction stage"""
        if not blocks:
            raise ValueError("No blocks to extract from. Please add data files to the input directory.")

        batch_size = self.config.get('extraction', {}).get('batch_size', 50)

        self.logger.info(f"Extracting knowledge graphs from {len(blocks)} blocks...")
        extraction_result = self.kg_builder.extract_from_blocks(blocks, batch_size)

        return extraction_result

    def _run_storage(self, extraction_result):
        """Run storage stage"""
        self.logger.info("Saving extraction results...")

        # Save all results
        saved_files = self.file_saver.save_all(extraction_result)

        # Save extractor state
        if self.config.get('output', {}).get('save_state', True):
            state_file = self.file_saver.save_state(self.kg_builder)
            saved_files['state'] = state_file

        self.logger.info(f"Created {len(saved_files)} output files")
        for file_type, filepath in saved_files.items():
            self.logger.info(f"  {file_type}: {filepath}")

        return saved_files

    def _run_neo4j_export(self, extraction_result):
        """Run Neo4j export stage"""
        if not self.neo4j_connector:
            self.logger.info("Neo4j export not enabled")
            return None

        try:
            self.logger.info("Exporting to Neo4j...")
            stats = self.neo4j_connector.export_knowledge_graph(
                extraction_result['entities'],
                extraction_result['relationships']
            )
            self.logger.info(f"Neo4j export completed: {stats}")
            return stats

        except Exception as e:
            self.monitor.record_error("Neo4j Export", str(e))
            self.logger.error(f"Neo4j export failed: {e}")
            return None
