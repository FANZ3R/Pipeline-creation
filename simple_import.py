"""
Simple, guaranteed-to-work relationship import
"""

import pandas as pd
from neo4j import GraphDatabase
import yaml
from tqdm import tqdm

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

neo4j_config = config['neo4j']
driver = GraphDatabase.driver(
    neo4j_config['uri'],
    auth=(neo4j_config['username'], neo4j_config['password'])
)

print("=" * 60)
print("SIMPLE RELATIONSHIP IMPORT")
print("=" * 60)

# Load relationships
rel_df = pd.read_csv("data/output/relationships_20250930_122401.csv")
print(f"\nTotal relationships to import: {len(rel_df):,}")

# Remove any existing relationships
with driver.session() as session:
    session.run("MATCH ()-[r]->() DELETE r")
    print("Cleared existing relationships")

# Import in small batches with simple logic
batch_size = 100  # Small batches to avoid memory issues
successful = 0
failed = 0
failed_examples = []

print("\nImporting relationships...")
with tqdm(total=len(rel_df), desc="Progress") as pbar:
    for i in range(0, len(rel_df), batch_size):
        batch_df = rel_df.iloc[i:i+batch_size]
        
        for _, row in batch_df.iterrows():
            with driver.session() as session:
                try:
                    # Simple, direct query
                    subject_text = str(row['subject_text'])
                    object_text = str(row['object_text'])
                    rel_type = str(row.get('discovered_type', 'RELATED'))[:50].upper().replace(' ', '_').replace('-', '_')
                    confidence = float(row.get('confidence', 0.5))
                    
                    result = session.run("""
                        MATCH (s:Entity {text: $subject_text})
                        MATCH (o:Entity {text: $object_text})
                        CREATE (s)-[r:RELATED {
                            type: $rel_type,
                            confidence: $confidence
                        }]->(o)
                        RETURN id(r) as rel_id
                    """,
                    subject_text=subject_text,
                    object_text=object_text,
                    rel_type=rel_type,
                    confidence=confidence)
                    
                    if result.single():
                        successful += 1
                    else:
                        failed += 1
                        if len(failed_examples) < 5:
                            failed_examples.append({
                                'subject': subject_text[:50],
                                'object': object_text[:50]
                            })
                        
                except Exception as e:
                    failed += 1
                    if len(failed_examples) < 5:
                        failed_examples.append({
                            'subject': str(row['subject_text'])[:50],
                            'object': str(row['object_text'])[:50],
                            'error': str(e)[:100]
                        })
            
            pbar.update(1)
            
            # Print progress every 10000
            if (successful + failed) % 10000 == 0:
                print(f"\n  Processed {successful + failed:,}: {successful:,} successful, {failed:,} failed")

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

if failed > 0 and failed_examples:
    print("\nExamples of failed imports:")
    for ex in failed_examples:
        print(f"  Subject: {ex.get('subject', 'N/A')}")
        print(f"  Object: {ex.get('object', 'N/A')}")
        if 'error' in ex:
            print(f"  Error: {ex['error']}")
        print()

if successful == 0:
    print("\n⚠️  NO RELATIONSHIPS IMPORTED!")
    print("Debugging suggestions:")
    print("1. Check if entities still exist: MATCH (e:Entity) RETURN count(e)")
    print("2. Try importing just one relationship manually in Neo4j Browser")
    print("3. Check Neo4j logs: docker logs neo4j")
else:
    print(f"\n✅ SUCCESS! Imported {successful:,} relationships!")
    print("You can now view your knowledge graph in Neo4j Browser at http://localhost:7474")