"""
Fixed Neo4j export using existing CSV files directly
Uses pandas + UNWIND for maximum efficiency
No JSON conversion needed - uses CSV files already in output folder
"""

import os
import yaml
import pandas as pd
from pathlib import Path
from datetime import datetime
from neo4j import GraphDatabase
from tqdm import tqdm
import logging


def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    return logging.getLogger(__name__)


def list_output_files():
    """List available CSV and JSON files in output directory"""
    output_dir = "data/output"
    
    if not os.path.exists(output_dir):
        print(f"Output directory not found: {output_dir}")
        return None, None, None, None
    
    # Get file info from filesystem
    entity_csv_files = []
    relationship_csv_files = []
    entity_json_files = []
    relationship_json_files = []
    
    for file_path in Path(output_dir).iterdir():
        if file_path.is_file():
            if "entities_" in file_path.name:
                if file_path.suffix == '.csv':
                    entity_csv_files.append(file_path)
                elif file_path.suffix == '.json':
                    entity_json_files.append(file_path)
            elif "relationships_" in file_path.name:
                if file_path.suffix == '.csv':
                    relationship_csv_files.append(file_path)
                elif file_path.suffix == '.json':
                    relationship_json_files.append(file_path)
    
    print(f"\nFiles found in {output_dir}:")
    
    if entity_csv_files or relationship_csv_files:
        print("\nCSV files (WILL BE USED):")
        for f in entity_csv_files:
            size_mb = f.stat().st_size / (1024*1024)
            mod_time = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            print(f"  ✓ {f.name} ({size_mb:.1f} MB, modified: {mod_time})")
        for f in relationship_csv_files:
            size_mb = f.stat().st_size / (1024*1024)
            mod_time = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            print(f"  ✓ {f.name} ({size_mb:.1f} MB, modified: {mod_time})")
    
    if entity_json_files or relationship_json_files:
        print("\nJSON files (available but not needed):")
        for f in entity_json_files + relationship_json_files:
            size_mb = f.stat().st_size / (1024*1024)
            print(f"  - {f.name} ({size_mb:.1f} MB)")
    
    # Get latest CSV files by modification time
    latest_entity_csv = max(entity_csv_files, key=lambda x: x.stat().st_mtime) if entity_csv_files else None
    latest_relationship_csv = max(relationship_csv_files, key=lambda x: x.stat().st_mtime) if relationship_csv_files else None
    latest_entity_json = max(entity_json_files, key=lambda x: x.stat().st_mtime) if entity_json_files else None
    latest_relationship_json = max(relationship_json_files, key=lambda x: x.stat().st_mtime) if relationship_json_files else None
    
    return latest_entity_csv, latest_relationship_csv, latest_entity_json, latest_relationship_json


class CSVNeo4jExporter:
    """Neo4j exporter using CSV files directly for maximum performance"""
    
    def __init__(self, uri, username, password):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.logger = logging.getLogger(__name__)
    
    def close(self):
        self.driver.close()
    
    def test_connection(self):
        """Test Neo4j connection"""
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def clear_and_setup(self, force_clear=True):
        """Fast database clear and constraint setup with batched operations"""
        try:
            with self.driver.session() as session:
                if force_clear:
                    print("Clearing existing data...")
                    # Clear in smaller batches to avoid memory issues
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
                        print(f"  Deleted {deleted} nodes...")
                    print("Database cleared")
                
                # Create constraint with smaller transaction
                try:
                    session.run("DROP CONSTRAINT entity_id IF EXISTS")
                except:
                    pass
                    
                session.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE")
                print("Created entity ID constraint")
                
                # Create text index for matching
                session.run("CREATE INDEX entity_text IF NOT EXISTS FOR (e:Entity) ON (e.text)")
                print("Created entity text index")
                
        except Exception as e:
            print(f"Setup warning: {e}")
    
    def get_csv_info(self, csv_file):
        """Get information about a CSV file without loading it"""
        # Count rows efficiently
        row_count = sum(1 for _ in open(csv_file)) - 1  # Subtract header
        
        # Get columns from first line
        with open(csv_file, 'r') as f:
            columns = f.readline().strip().split(',')
        
        return {
            'rows': row_count,
            'columns': columns,
            'size_mb': csv_file.stat().st_size / (1024*1024)
        }
    
    def bulk_import_entities_csv(self, csv_file, batch_size=2000):
        """Import entities directly from CSV using pandas chunking"""
        print(f"\nImporting entities from CSV: {csv_file.name}")
        
        # Get file info
        info = self.get_csv_info(csv_file)
        print(f"  Rows: {info['rows']:,}")
        print(f"  Columns: {', '.join(info['columns'][:5])}...")
        print(f"  Size: {info['size_mb']:.1f} MB")
        
        total_imported = 0
        
        # Use pandas chunking for memory efficiency
        chunks = pd.read_csv(csv_file, chunksize=batch_size)
        
        with tqdm(total=info['rows'], desc="Importing entities") as pbar:
            for chunk_df in chunks:
                # Fill NaN values with defaults
                chunk_df = chunk_df.fillna({
                    'confidence': 0.0,
                    'source': 'unknown',
                    'block_id': -1,
                    'text': '',
                    'label': 'UNKNOWN'
                })
                
                batch = chunk_df.to_dict('records')
                
                # Use smaller transactions
                with self.driver.session() as session:
                    session.run("""
                        UNWIND $batch as entity
                        MERGE (e:Entity {id: entity.id})
                        SET e.text = coalesce(entity.text, ''),
                            e.label = coalesce(entity.label, 'UNKNOWN'),
                            e.confidence = toFloat(coalesce(entity.confidence, 0)),
                            e.source = coalesce(entity.source, 'unknown'),
                            e.block_id = coalesce(entity.block_id, -1)
                    """, batch=batch)
                
                total_imported += len(batch)
                pbar.update(len(batch))
        
        print(f"✓ Imported {total_imported:,} entities")
        return total_imported
    
    def bulk_import_relationships_csv(self, csv_file, batch_size=1000, min_confidence=None):
        """Import relationships from CSV - matching entities by TEXT"""
        print(f"\nImporting relationships from CSV: {csv_file.name}")
        print("NOTE: Matching entities by TEXT field")
        
        # Get file info
        info = self.get_csv_info(csv_file)
        print(f"  Rows: {info['rows']:,}")
        print(f"  Columns: {', '.join(info['columns'])}")
        print(f"  Size: {info['size_mb']:.1f} MB")
        
        # Read first few rows to understand structure
        sample_df = pd.read_csv(csv_file, nrows=5)
        print(f"\nDetected columns: {sample_df.columns.tolist()}")
        
        total_processed = 0
        total_imported = 0
        failed_count = 0
        skipped_count = 0
        
        # Use pandas chunking
        chunks = pd.read_csv(csv_file, chunksize=batch_size)
        
        with tqdm(total=info['rows'], desc="Importing relationships") as pbar:
            for chunk_df in chunks:
                total_processed += len(chunk_df)
                
                # Identify columns
                subject_col = None
                object_col = None
                
                if 'subject_text' in chunk_df.columns and 'object_text' in chunk_df.columns:
                    subject_col = 'subject_text'
                    object_col = 'object_text'
                elif 'subject' in chunk_df.columns and 'object' in chunk_df.columns:
                    subject_col = 'subject'
                    object_col = 'object'
                
                if not subject_col or not object_col:
                    print(f"Warning: Could not find text columns")
                    pbar.update(len(chunk_df))
                    continue
                
                # Skip rows with NaN
                original_len = len(chunk_df)
                chunk_df = chunk_df.dropna(subset=[subject_col, object_col])
                skipped_count += (original_len - len(chunk_df))
                
                if len(chunk_df) == 0:
                    pbar.update(original_len)
                    continue
                
                # Apply confidence filter if specified
                if min_confidence is not None and 'confidence' in chunk_df.columns:
                    chunk_df = chunk_df[chunk_df['confidence'] >= min_confidence]
                
                # Fill NaN values
                chunk_df = chunk_df.fillna({
                    'confidence': 0.5,
                    'source': '',
                    'sources': '',
                    'discovered_type': 'RELATED',
                    'block_id': -1
                })
                
                batch = chunk_df.to_dict('records')
                
                # Process batch
                for rel in batch:
                    rel['subject_text'] = str(rel[subject_col]).strip()
                    rel['object_text'] = str(rel[object_col]).strip()
                    
                    rel_type = (rel.get('discovered_type') or 
                               rel.get('relation') or 
                               'RELATED')
                    rel['relationship_type'] = str(rel_type).upper().replace(' ', '_').replace('-', '_')[:50]  # Limit length
                    
                    if 'source' not in rel or not rel['source']:
                        if 'sources' in rel:
                            rel['source'] = str(rel['sources'])
                
                try:
                    with self.driver.session() as session:
                        result = session.run("""
                            UNWIND $batch as rel
                            MATCH (s:Entity {text: rel.subject_text})
                            MATCH (o:Entity {text: rel.object_text})
                            CREATE (s)-[r:RELATED {
                                type: rel.relationship_type,
                                confidence: toFloat(coalesce(rel.confidence, 0.5)),
                                source: coalesce(rel.source, ''),
                                block_id: coInteger(coalesce(rel.block_id, -1))
                            }]->(o)
                            RETURN count(r) as created_count
                        """, batch=batch)
                        
                        created = result.single()['created_count']
                        total_imported += created
                        
                        if created < len(batch):
                            failed_count += (len(batch) - created)
                            
                except Exception as e:
                    failed_count += len(batch)
                    if failed_count <= 5:
                        self.logger.warning(f"Failed batch: {str(e)[:100]}")
                
                pbar.update(original_len)
        
        print(f"\n✓ Processed {total_processed:,} relationship rows")
        print(f"✓ Successfully imported {total_imported:,} relationships")
        if skipped_count > 0:
            print(f"⚠ Skipped {skipped_count:,} rows (missing data)")
        if failed_count > 0:
            print(f"⚠ Failed: {failed_count:,} (entities not found)")
        
        return total_processed, total_imported
    
    def get_stats(self):
        """Get database statistics"""
        with self.driver.session() as session:
            stats = {}
            
            # Count nodes
            result = session.run("MATCH (n) RETURN count(n) as count")
            stats['total_nodes'] = result.single()['count']
            
            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            stats['total_relationships'] = result.single()['count']
            
            # Entity type distribution
            result = session.run("""
                MATCH (n:Entity) 
                RETURN n.label as type, count(*) as count 
                ORDER BY count DESC 
                LIMIT 10
            """)
            stats['top_entity_types'] = [
                {"type": record["type"], "count": record["count"]} 
                for record in result
            ]
            
            # Relationship type distribution
            result = session.run("""
                MATCH ()-[r:RELATED]->() 
                RETURN r.type as type, count(*) as count 
                ORDER BY count DESC 
                LIMIT 10
            """)
            stats['top_relationship_types'] = [
                {"type": record["type"], "count": record["count"]} 
                for record in result
            ]
            
            return stats


def main():
    logger = setup_logging()
    
    print("=" * 60)
    print("NEO4J CSV IMPORT TOOL")
    print("=" * 60)
    
    # List files
    entity_csv, rel_csv, entity_json, rel_json = list_output_files()
    
    if not entity_csv or not rel_csv:
        print("\n❌ No CSV files found in data/output/")
        print("   Run the main pipeline first: python main.py")
        return
    
    # Show selected files
    entity_size = entity_csv.stat().st_size / (1024*1024)
    rel_size = rel_csv.stat().st_size / (1024*1024)
    
    print(f"\n📁 Selected CSV files for import:")
    print(f"   Entities: {entity_csv.name} ({entity_size:.1f} MB)")
    print(f"   Relationships: {rel_csv.name} ({rel_size:.1f} MB)")
    
    # User confirmation
    print(f"\nReady to import to Neo4j?")
    choice = input("   Enter 'y' to proceed, 'n' to cancel: ").lower().strip()
    
    if choice != 'y':
        print("Import cancelled.")
        return
    
    # Load Neo4j config
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("❌ config.yaml not found!")
        return
    
    neo4j_config = config.get('neo4j', {})
    
    print(f"\n🔗 Neo4j configuration:")
    print(f"   URI: {neo4j_config['uri']}")
    print(f"   Username: {neo4j_config['username']}")
    
    # Test connection
    print(f"\n🔌 Testing Neo4j connection...")
    exporter = CSVNeo4jExporter(
        neo4j_config['uri'],
        neo4j_config['username'], 
        neo4j_config['password']
    )
    
    if not exporter.test_connection():
        exporter.close()
        return
    
    print("✓ Connection successful!")
    
    try:
        # Clear and setup database
        clear_db = neo4j_config.get('clear_database', True)
        if clear_db:
            confirm_clear = input("\n⚠️  Clear existing database? (y/n): ").lower().strip()
            clear_db = (confirm_clear == 'y')
        
        exporter.clear_and_setup(force_clear=clear_db)
        
        # Performance settings
        use_filtering = neo4j_config.get('use_confidence_filter', False)
        confidence_threshold = neo4j_config.get('confidence_threshold', 0.5) if use_filtering else None
        entity_batch_size = neo4j_config.get('entity_batch_size', 2000)
        rel_batch_size = neo4j_config.get('relationship_batch_size', 1000)
        
        print(f"\n⚙️  Import settings:")
        print(f"   Entity batch size: {entity_batch_size:,}")
        print(f"   Relationship batch size: {rel_batch_size:,}")
        if use_filtering:
            print(f"   Confidence threshold: {confidence_threshold}")
        else:
            print(f"   Confidence filtering: DISABLED (importing ALL relationships)")
        
        start_time = datetime.now()
        print(f"\n🚀 Starting import at {start_time.strftime('%H:%M:%S')}...")
        
        # Import entities from CSV
        entities_imported = exporter.bulk_import_entities_csv(
            entity_csv, 
            batch_size=entity_batch_size
        )
        
        # Import relationships from CSV
        total_rels, imported_rels = exporter.bulk_import_relationships_csv(
            rel_csv, 
            batch_size=rel_batch_size,
            min_confidence=confidence_threshold
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Get final statistics
        print("\n📊 Getting database statistics...")
        stats = exporter.get_stats()
        
        # Final summary
        print("\n" + "=" * 60)
        print("✅ IMPORT COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"⏱️  Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        print(f"📈 Performance: {(entities_imported + imported_rels)/duration:.0f} items/second")
        print(f"\n📊 Import Summary:")
        print(f"   Entities imported: {entities_imported:,}")
        print(f"   Relationships processed: {total_rels:,}")
        print(f"   Relationships imported: {imported_rels:,}")
        if total_rels > 0:
            print(f"   Success rate: {(imported_rels/total_rels)*100:.1f}%")
        
        print(f"\n🗄️  Database Status:")
        print(f"   Total nodes: {stats['total_nodes']:,}")
        print(f"   Total relationships: {stats['total_relationships']:,}")
        
        if stats['top_entity_types']:
            print(f"\n🏷️  Top Entity Types:")
            for et in stats['top_entity_types'][:5]:
                print(f"   - {et['type']}: {et['count']:,}")
        
        if stats['top_relationship_types']:
            print(f"\n🔗 Top Relationship Types:")
            for rt in stats['top_relationship_types'][:5]:
                print(f"   - {rt['type']}: {rt['count']:,}")
        
        print(f"\n🌐 Access Neo4j Browser at: http://localhost:7474")
        print(f"   Connect to: {neo4j_config['uri']}")
        
    except KeyboardInterrupt:
        print("\n⚠️  Import interrupted by user")
    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        logger.error(f"Import error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        exporter.close()


if __name__ == "__main__":
    main()