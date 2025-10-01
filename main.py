"""
Main script for Knowledge Graph extraction with proper relationship mapping
Usage: python main.py
"""

import os
import yaml
import logging
from datetime import datetime
import spacy

from pipeline.data_loader import DataLoader
from pipeline.kg_extractor import GeneralizedKnowledgeGraphExtractor
from pipeline.output_saver import OutputSaver


def setup_logging():
    """Simple logging setup"""
    os.makedirs("logs", exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        handlers=[
            logging.FileHandler("logs/pipeline.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def load_config():
    """Load configuration"""
    default_config = {
        'input_directory': 'data/input',
        'output_directory': 'data/output',
        'spacy_model': 'en_core_web_sm',
        'batch_size': 50,
        'neo4j': {
            'enabled': False,
            'uri': 'bolt://localhost:7688',
            'username': 'neo4j',
            'password': 'password123',
            'clear_database': True,
            'use_confidence_filter': False,
            'entity_batch_size': 2000,
            'relationship_batch_size': 1000
        }
    }
    
    if os.path.exists('config.yaml'):
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        # Merge with defaults
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
    else:
        config = default_config
        # Create config file
        with open('config.yaml', 'w') as f:
            yaml.dump(config, f, indent=2)
        print("Created config.yaml - you can customize settings there")
    
    return config


def main():
    """Main pipeline execution with fixed relationship mapping"""
    
    print("=" * 60)
    print("KNOWLEDGE GRAPH EXTRACTION PIPELINE")
    print("=" * 60)
    
    # Setup
    logger = setup_logging()
    config = load_config()
    start_time = datetime.now()
    
    # Create directories
    os.makedirs(config['input_directory'], exist_ok=True)
    os.makedirs(config['output_directory'], exist_ok=True)
    
    try:
        # 1. Initialize components
        logger.info("Initializing components...")
        
        data_loader = DataLoader()
        output_saver = OutputSaver(config['output_directory'])  # Use OutputSaver
        
        # Load spaCy model
        try:
            nlp = spacy.load(config['spacy_model'])
            logger.info(f"Loaded spaCy model: {config['spacy_model']}")
        except OSError:
            print(f"Error: spaCy model '{config['spacy_model']}' not found")
            print(f"Install with: python -m spacy download {config['spacy_model']}")
            return
        
        # Initialize your original KG extractor
        kg_extractor = GeneralizedKnowledgeGraphExtractor(nlp)
        
        # 2. Load data
        logger.info("Loading input data...")
        
        if not os.listdir(config['input_directory']):
            print(f"\nNo files found in {config['input_directory']}")
            print("Please add your data files (JSON, CSV, TXT, PDF, DOCX) and run again")
            return
        
        text_blocks = data_loader.load_all_from_directory(config['input_directory'])
        
        if not text_blocks:
            print("No text content found in input files")
            return
        
        print(f"Loaded {len(text_blocks)} text blocks")
        
        # 3. Extract knowledge graphs
        logger.info("Extracting knowledge graphs...")
        
        all_entities = []
        all_relationships = []
        
        # Process in batches
        batch_size = config.get('batch_size', 50)
        
        for i in range(0, len(text_blocks), batch_size):
            batch = text_blocks[i:i+batch_size]
            print(f"Processing batch {i//batch_size + 1}/{(len(text_blocks) + batch_size - 1)//batch_size}")
            
            for block in batch:
                try:
                    # Your original extraction
                    kg_result = kg_extractor.extract_knowledge_graph(block['text'])
                    
                    # Add source info to entities
                    for entity in kg_result['entities']:
                        entity['source_file'] = block['source']
                        entity['block_id'] = block['block_id']
                        all_entities.append(entity)
                    
                    # Relationships already have full entity objects
                    for relationship in kg_result['relationships']:
                        relationship['source_file'] = block['source']
                        relationship['block_id'] = block['block_id']
                        all_relationships.append(relationship)
                        
                except Exception as e:
                    logger.error(f"Failed to process block {block['block_id']}: {e}")
                    continue
        
        # 4. Save results using OutputSaver (which now has the correct structure)
        logger.info("Saving results...")
        
        files_saved = output_saver.save_results(all_entities, all_relationships)
        
        # Optionally save to Neo4j if enabled
        if config['neo4j']['enabled']:
            logger.info("Exporting to Neo4j...")
            output_saver.save_to_neo4j(all_entities, all_relationships, config['neo4j'])
        
        # 5. Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print("PIPELINE COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"⏱️  Duration: {duration:.2f} seconds ({duration/60:.1f} minutes)")
        print(f"📄 Text blocks processed: {len(text_blocks):,}")
        print(f"🔵 Entities extracted: {len(all_entities):,}")
        print(f"🔗 Relationships extracted: {len(all_relationships):,}")
        print(f"📁 Results saved to: {config['output_directory']}")
        
        # Entity statistics
        entity_types = {}
        for entity in all_entities:
            label = entity.get('label', 'UNKNOWN')
            entity_types[label] = entity_types.get(label, 0) + 1
        
        print(f"\n📊 Top entity types:")
        for entity_type, count in sorted(entity_types.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  - {entity_type}: {count:,}")
        
        # Relationship statistics
        rel_types = {}
        for rel in all_relationships:
            rel_type = rel.get('discovered_type', 'UNKNOWN')
            rel_types[rel_type] = rel_types.get(rel_type, 0) + 1
        
        print(f"\n🔗 Top relationship types:")
        for rel_type, count in sorted(rel_types.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  - {rel_type}: {count:,}")
        
        # Prompt for Neo4j export
        if not config['neo4j']['enabled']:
            print("\n💡 Tip: To export to Neo4j, run: python fast_export.py")
        else:
            print("\n✅ Neo4j export completed")
        
        logger.info("Pipeline completed successfully")
        
    except KeyboardInterrupt:
        print("\nPipeline interrupted by user")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    main()