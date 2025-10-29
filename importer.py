"""
Neo4j Importer - Fast CSV streaming import
Imports entities and relationships directly from CSV files to Neo4j

Usage:
    python neo4j_importer.py
"""

import pandas as pd
from pathlib import Path
from neo4j import GraphDatabase
from tqdm import tqdm
import logging
import os
from datetime import datetime

# Setup logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/neo4j_import_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
CONFIG = {
    'output_dir': 'kg_output',
    'neo4j_uri': 'bolt://localhost:7687',
    'neo4j_user': 'neo4j',
    'neo4j_password': 'your_secure_password',  # UPDATE THIS
    'entity_batch_size': 5000,
    'relationship_batch_size': 5000
}


def find_latest_csv_files(output_dir):
    """Find the latest CSV files"""
    output_path = Path(output_dir)
    
    if not output_path.exists():
        logger.error(f"Output directory not found: {output_dir}")
        return None, None
    
    entity_files = sorted(output_path.glob('entities_*.csv'), key=lambda x: x.stat().st_mtime, reverse=True)
    rel_files = sorted(output_path.glob('relationships_*.csv'), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not entity_files or not rel_files:
        logger.error("No CSV files found")
        return None, None
    
    return str(entity_files[0]), str(rel_files[0])


def get_file_row_count(filepath):
    """Get number of rows in CSV file"""
    with open(filepath, 'r') as f:
        return sum(1 for _ in f) - 1  # Subtract header


def clear_database(driver):
    """Clear existing Neo4j database"""
    logger.info("Clearing existing database...")
    with driver.session() as session:
        # Delete in batches to avoid memory issues
        while True:
            result = session.run("""
                MATCH (n)
                WITH n LIMIT 10000
                DETACH DELETE n
                RETURN count(n) as deleted
            """)
            deleted = result.single()['deleted']
            if deleted == 0:
                break
            logger.info(f"  Deleted {deleted} nodes...")
    
    logger.info("Database cleared successfully")


def create_constraints(driver):
    """Create database constraints"""
    logger.info("Creating constraints...")
    with driver.session() as session:
        try:
            session.run("DROP CONSTRAINT entity_id IF EXISTS")
        except:
            pass
        
        session.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE")
        logger.info("Created entity ID constraint")


def import_entities_from_csv(driver, csv_file, batch_size):
    """Import entities from CSV in batches"""
    logger.info(f"Importing entities from: {csv_file}")
    
    # Get total count for progress bar
    total_rows = get_file_row_count(csv_file)
    logger.info(f"Total entities to import: {total_rows:,}")
    
    imported = 0
    
    # Stream CSV in chunks
    with tqdm(total=total_rows, desc="Importing entities", unit="entities") as pbar:
        for chunk in pd.read_csv(csv_file, chunksize=batch_size):
            # Fill NaN values
            chunk = chunk.fillna({
                'confidence': 0.0,
                'source': 'unknown',
                'block_id': -1,
                'text': '',
                'label': 'UNKNOWN'
            })
            
            batch = chunk.to_dict('records')
            
            with driver.session() as session:
                session.run("""
                    UNWIND $batch as entity
                    CREATE (e:Entity {
                        id: entity.id,
                        text: entity.text,
                        label: entity.label,
                        confidence: toFloat(entity.confidence),
                        source: entity.source,
                        block_id: toInteger(entity.block_id)
                    })
                """, batch=batch)
            
            imported += len(batch)
            pbar.update(len(batch))
    
    logger.info(f"Imported {imported:,} entities")
    return imported


def import_relationships_from_csv(driver, csv_file, batch_size):
    """Import relationships from CSV in batches"""
    logger.info(f"Importing relationships from: {csv_file}")
    
    # Get total count
    total_rows = get_file_row_count(csv_file)
    logger.info(f"Total relationships to import: {total_rows:,}")
    
    imported = 0
    failed = 0
    
    with tqdm(total=total_rows, desc="Importing relationships", unit="rels") as pbar:
        for chunk in pd.read_csv(csv_file, chunksize=batch_size):
            # Fill NaN values
            chunk = chunk.fillna({
                'confidence': 0.5,
                'source': '',
                'discovered_type': 'RELATED',
                'block_id': -1
            })
            
            # Drop rows with missing entity IDs
            chunk = chunk.dropna(subset=['subject_id', 'object_id'])
            
            batch = []
            for _, row in chunk.iterrows():
                rel_type = str(row['discovered_type']).upper().replace(' ', '_').replace('-', '_')[:50]
                
                batch.append({
                    'subject_id': str(row['subject_id']),
                    'object_id': str(row['object_id']),
                    'rel_type': rel_type,
                    'confidence': float(row['confidence']),
                    'source': str(row.get('source', '')),
                    'block_id': int(row.get('block_id', -1))
                })
            
            if batch:
                with driver.session() as session:
                    try:
                        result = session.run("""
                            UNWIND $batch as rel
                            MATCH (s:Entity {id: rel.subject_id})
                            MATCH (o:Entity {id: rel.object_id})
                            CREATE (s)-[r:RELATED {
                                type: rel.rel_type,
                                confidence: rel.confidence,
                                source: rel.source,
                                block_id: rel.block_id
                            }]->(o)
                            RETURN count(r) as created
                        """, batch=batch)
                        
                        created = result.single()['created']
                        imported += created
                        failed += (len(batch) - created)
                        
                    except Exception as e:
                        logger.error(f"Batch error: {str(e)[:100]}")
                        failed += len(batch)
            
            pbar.update(len(chunk))
    
    logger.info(f"Imported {imported:,} relationships")
    if failed > 0:
        logger.warning(f"Failed to import {failed:,} relationships (entities not found)")
    
    return imported, failed


def get_statistics(driver):
    """Get database statistics"""
    with driver.session() as session:
        stats = {}
        
        result = session.run("MATCH (n) RETURN count(n) as count")
        stats['total_nodes'] = result.single()['count']
        
        result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
        stats['total_relationships'] = result.single()['count']
        
        result = session.run("""
            MATCH (n:Entity) 
            RETURN n.label as type, count(*) as count 
            ORDER BY count DESC 
            LIMIT 10
        """)
        stats['entity_types'] = result.data()
        
        return stats


def main():
    logger.info("=" * 60)
    logger.info("NEO4J KNOWLEDGE GRAPH IMPORTER")
    logger.info("Fast CSV streaming import")
    logger.info("=" * 60)
    
    # Find latest CSV files
    logger.info(f"Searching for CSV files in {CONFIG['output_dir']}...")
    entities_file, relationships_file = find_latest_csv_files(CONFIG['output_dir'])
    
    if not entities_file or not relationships_file:
        return
    
    logger.info(f"Found entities file: {Path(entities_file).name}")
    logger.info(f"Found relationships file: {Path(relationships_file).name}")
    
    print("\n" + "=" * 60)
    print("IMPORT CONFIGURATION")
    print("=" * 60)
    print(f"Entities CSV:       {entities_file}")
    print(f"Relationships CSV:  {relationships_file}")
    print(f"Neo4j URI:          {CONFIG['neo4j_uri']}")
    print(f"Neo4j User:         {CONFIG['neo4j_user']}")
    print(f"Entity batch size:  {CONFIG['entity_batch_size']:,}")
    print(f"Rel batch size:     {CONFIG['relationship_batch_size']:,}")
    print("=" * 60 + "\n")
    
    # Connect to Neo4j
    logger.info("Connecting to Neo4j...")
    try:
        driver = GraphDatabase.driver(
            CONFIG['neo4j_uri'],
            auth=(CONFIG['neo4j_user'], CONFIG['neo4j_password'])
        )
        
        with driver.session() as session:
            session.run("RETURN 1")
        
        logger.info("Connected successfully!")
        
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        logger.error("Make sure Neo4j is running and credentials are correct")
        return
    
    start_time = datetime.now()
    
    try:
        # Step 1: Clear database
        clear_database(driver)
        
        # Step 2: Create constraints
        create_constraints(driver)
        
        # Step 3: Import entities
        entities_imported = import_entities_from_csv(
            driver,
            entities_file,
            CONFIG['entity_batch_size']
        )
        
        # Step 4: Import relationships
        rels_imported, rels_failed = import_relationships_from_csv(
            driver,
            relationships_file,
            CONFIG['relationship_batch_size']
        )
        
        # Step 5: Get final statistics
        logger.info("Getting final statistics...")
        stats = get_statistics(driver)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Print summary
        logger.info("=" * 60)
        logger.info("IMPORT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Duration: {duration:.2f}s ({duration/60:.1f} minutes)")
        logger.info(f"Entities imported:      {entities_imported:,}")
        logger.info(f"Relationships imported: {rels_imported:,}")
        logger.info(f"Relationships failed:   {rels_failed:,}")
        logger.info(f"Final nodes in DB:      {stats['total_nodes']:,}")
        logger.info(f"Final rels in DB:       {stats['total_relationships']:,}")
        logger.info("\nTop entity types:")
        for et in stats['entity_types'][:5]:
            logger.info(f"  {et['type']}: {et['count']:,}")
        logger.info("=" * 60)
        
        print("\n" + "=" * 60)
        print("✅ IMPORT SUCCESSFUL!")
        print("=" * 60)
        print(f"Duration: {duration/60:.1f} minutes")
        print(f"Nodes: {stats['total_nodes']:,}")
        print(f"Relationships: {stats['total_relationships']:,}")
        print(f"\nView in Neo4j Browser: http://localhost:7474")
        print("=" * 60)
        
    finally:
        driver.close()


if __name__ == "__main__":
    main()