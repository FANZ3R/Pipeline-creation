"""
Simple output saver - saves results to JSON and CSV with proper structure for Neo4j
"""

import json
import pandas as pd
import os
from datetime import datetime


class OutputSaver:
    """Simple saver for knowledge graph results"""
    
    def __init__(self, output_dir="data/output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def save_results(self, entities, relationships):
        """Save entities and relationships with proper structure"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save entities JSON
        entities_file = f"{self.output_dir}/entities_{timestamp}.json"
        with open(entities_file, 'w', encoding='utf-8') as f:
            json.dump(entities, f, indent=2, ensure_ascii=False)
        
        # Save relationships JSON
        relations_file = f"{self.output_dir}/relationships_{timestamp}.json"
        with open(relations_file, 'w', encoding='utf-8') as f:
            json.dump(relationships, f, indent=2, ensure_ascii=False)
        
        # Save entities CSV
        if entities:
            entities_df = pd.DataFrame(entities)
            entities_csv = f"{self.output_dir}/entities_{timestamp}.csv"
            entities_df.to_csv(entities_csv, index=False)
        
        # Save relationships CSV with PROPER structure for Neo4j matching
        if relationships:
            simple_rels = []
            for rel in relationships:
                # Extract subject and object properly
                subject_info = rel.get('subject', {})
                object_info = rel.get('object', {})
                
                # Handle both dict and string formats
                if isinstance(subject_info, dict):
                    subject_text = subject_info.get('text', '')
                    subject_id = subject_info.get('id', '')
                else:
                    subject_text = str(subject_info)
                    subject_id = ''
                
                if isinstance(object_info, dict):
                    object_text = object_info.get('text', '')
                    object_id = object_info.get('id', '')
                else:
                    object_text = str(object_info)
                    object_id = ''
                
                # Create row with all necessary fields
                simple_rels.append({
                    'id': rel.get('id', ''),
                    'subject_text': subject_text,  # For Neo4j text matching
                    'subject_id': subject_id,      # Keep for reference
                    'discovered_type': rel.get('discovered_type', 'RELATED'),
                    'object_text': object_text,    # For Neo4j text matching  
                    'object_id': object_id,        # Keep for reference
                    'confidence': rel.get('confidence', 0.5),
                    'source': ', '.join(rel.get('sources', [])) if isinstance(rel.get('sources'), list) else str(rel.get('source', '')),
                    'block_id': rel.get('block_id', -1)
                })
            
            relations_df = pd.DataFrame(simple_rels)
            relations_csv = f"{self.output_dir}/relationships_{timestamp}.csv"
            relations_df.to_csv(relations_csv, index=False)
        
        # Summary
        summary = {
            'timestamp': timestamp,
            'total_entities': len(entities),
            'total_relationships': len(relationships),
            'entity_types': {},
            'relation_types': {}
        }
        
        # Count types
        for entity in entities:
            label = entity.get('label', 'UNKNOWN')
            summary['entity_types'][label] = summary['entity_types'].get(label, 0) + 1
        
        for rel in relationships:
            rel_type = rel.get('discovered_type', 'UNKNOWN')
            summary['relation_types'][rel_type] = summary['relation_types'].get(rel_type, 0) + 1
        
        # Save summary
        summary_file = f"{self.output_dir}/summary_{timestamp}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\nResults saved:")
        print(f"  Entities: {len(entities)}")
        print(f"  Relationships: {len(relationships)}")
        print(f"  Files: {self.output_dir}/")
        
        return {
            'entities_file': entities_file,
            'relationships_file': relations_file,
            'summary_file': summary_file
        }
    
    def save_to_neo4j(self, entities, relationships, neo4j_config):
        """Optional Neo4j export - now with text-based matching"""
        try:
            from neo4j import GraphDatabase
            
            driver = GraphDatabase.driver(
                neo4j_config['uri'],
                auth=(neo4j_config['username'], neo4j_config['password'])
            )
            
            with driver.session() as session:
                # Clear if requested
                if neo4j_config.get('clear_database', False):
                    session.run("MATCH (n) DETACH DELETE n")
                
                # Create index for text matching
                session.run("CREATE INDEX entity_text IF NOT EXISTS FOR (e:Entity) ON (e.text)")
                
                # Add entities
                for entity in entities:
                    session.run("""
                        MERGE (e:Entity {text: $text})
                        SET e.id = $id,
                            e.label = $label,
                            e.confidence = $confidence
                    """, 
                    id=entity['id'],
                    text=entity['text'],
                    label=entity['label'],
                    confidence=entity.get('confidence', 0)
                    )
                
                # Add relationships - matching by TEXT not ID
                for rel in relationships:
                    subject_info = rel.get('subject', {})
                    object_info = rel.get('object', {})
                    
                    # Get text for matching
                    if isinstance(subject_info, dict):
                        subject_text = subject_info.get('text', '')
                    else:
                        subject_text = str(subject_info)
                    
                    if isinstance(object_info, dict):
                        object_text = object_info.get('text', '')
                    else:
                        object_text = str(object_info)
                    
                    if subject_text and object_text:
                        session.run("""
                            MATCH (s:Entity {text: $subject_text})
                            MATCH (o:Entity {text: $object_text})
                            CREATE (s)-[r:RELATED {
                                type: $rel_type,
                                confidence: $confidence
                            }]->(o)
                        """,
                        subject_text=subject_text,
                        object_text=object_text,
                        rel_type=rel.get('discovered_type', 'RELATED'),
                        confidence=rel.get('confidence', 0)
                        )
            
            driver.close()
            print(f"Neo4j export complete: {len(entities)} entities, {len(relationships)} relationships")
            
        except ImportError:
            print("Neo4j driver not available. Install: pip install neo4j")
        except Exception as e:
            print(f"Neo4j export failed: {e}")