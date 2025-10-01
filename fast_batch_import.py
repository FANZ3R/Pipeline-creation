"""
Fast batch import using proper UNWIND operations
"""

import pandas as pd
from neo4j import GraphDatabase
import yaml
from tqdm import tqdm
import logging

# Suppress deprecation warnings
logging.getLogger("neo4j").setLevel(logging.ERROR)

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

neo4j_config = config['neo4j']
driver = GraphDatabase.driver(
    neo4j_config['uri'],
    auth=(neo4j_config['username'], neo4j_config['password'])
)

print("=" * 60)
print("FAST BATCH RELATIONSHIP IMPORT")
print("=" * 60)

# Load relationships
rel_df = pd.read_csv("data/output/relationships_20250930_122401.csv")
print(f"\nTotal relationships to import: {len(rel_df):,}")

# Clean existing relationships
with driver.session() as session:
    session.run("MATCH ()-[r]->() DELETE r")
    print("Cleared existing relationships")

# Process in larger batches for speed
BATCH_SIZE = 5000  # Much larger batches
successful = 0
failed = 0

print("\nImporting relationships in batches...")
with tqdm(total=len(rel_df), desc="Progress") as pbar:
    for i in range(0, len(rel_df), BATCH_SIZE):
        batch_df = rel_df.iloc[i:i+BATCH_SIZE]
        
        # Prepare batch data
        batch_data = []
        for _, row in batch_df.iterrows():
            batch_data.append({
                'subject_text': str(row['subject_text']),
                'object_text': str(row['object_text']),
                'rel_type': str(row.get('discovered_type', 'RELATED'))[:50].upper().replace(' ', '_').replace('-', '_'),
                'confidence': float(row.get('confidence', 0.5))
            })
        
        # Single transaction for entire batch
        with driver.session() as session:
            try:
                # Use UNWIND for batch processing
                result = session.run("""
                    UNWIND $batch as rel
                    MATCH (s:Entity {text: rel.subject_text})
                    MATCH (o:Entity {text: rel.object_text})
                    CREATE (s)-[r:RELATED {
                        type: rel.rel_type,
                        confidence: rel.confidence
                    }]->(o)
                    RETURN count(r) as created_count
                """, batch=batch_data)
                
                created = result.single()['created_count']
                successful += created
                failed += (len(batch_data) - created)
                
            except Exception as e:
                print(f"\nBatch error: {str(e)[:100]}")
                failed += len(batch_data)
        
        pbar.update(len(batch_df))
        
        # Print progress every 100k
        if (i + BATCH_SIZE) % 100000 == 0:
            print(f"\n  Processed {i+BATCH_SIZE:,}: {successful:,} successful, {failed:,} failed")

# Final check
with driver.session() as session:
    result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
    total_rels = result.single()['count']
    
    result = session.run("MATCH (n) RETURN count(n) as count")
    total_nodes = result.single()['count']

driver.close()

print("\n" + "=" * 60)
print("IMPORT COMPLETE")
print("=" * 60)
print(f"✓ Successfully imported: {successful:,} relationships")
print(f"✗ Failed: {failed:,} relationships")
print(f"📊 Total relationships in database: {total_rels:,}")
print(f"📊 Total nodes in database: {total_nodes:,}")

if successful > 0:
    print(f"\n✅ SUCCESS! Imported {successful:,} relationships!")
    print("You can now view your knowledge graph in Neo4j Browser at http://localhost:7474")
    print("\nSample Cypher queries to explore:")
    print("  MATCH (n) RETURN n LIMIT 25")
    print("  MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 50")
    print("  MATCH (n:Entity {label:'ORG'})-[r]->(m) RETURN n,r,m LIMIT 50")
else:
    print("\n⚠️ NO RELATIONSHIPS IMPORTED!")
    print("\nThis means the entity text values don't match.")
    print("Try running the full pipeline again from scratch:")
    print("  1. Clear database")
    print("  2. python main.py")
    print("  3. python fast_batch_import.py")