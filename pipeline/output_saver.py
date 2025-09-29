"""
Simple output saver - saves results to JSON and CSV
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
        """Save entities and relationships"""
        
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
        
        # Save relationships CSV (simplified)
        if relationships:
            simple_rels = []
            for rel in relationships:
                simple_rels.append({
                    'subject': rel.get('subject', {}).get('text', ''),
                    'relation': rel.get('discovered_type', ''),
                    'object': rel.get('object', {}).get('text', ''),
                    'confidence': rel.get('confidence', 0),
                    'sources': ', '.join(rel.get('sources', []))
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
        """Optional Neo4j export"""
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
                
                # Add entities
                for entity in entities:
                    session.run("""
                        CREATE (e:Entity {
                            id: $id,
                            text: $text,
                            label: $label,
                            confidence: $confidence
                        })
                    """, 
                    id=entity['id'],
                    text=entity['text'],
                    label=entity['label'],
                    confidence=entity.get('confidence', 0)
                    )
                
                # Add relationships
                for rel in relationships:
                    subject_id = rel.get('subject', {}).get('id')
                    object_id = rel.get('object', {}).get('id')
                    
                    if subject_id and object_id:
                        session.run("""
                            MATCH (s:Entity {id: $subject_id})
                            MATCH (o:Entity {id: $object_id})
                            CREATE (s)-[r:RELATED {
                                type: $rel_type,
                                confidence: $confidence
                            }]->(o)
                        """,
                        subject_id=subject_id,
                        object_id=object_id,
                        rel_type=rel.get('discovered_type', ''),
                        confidence=rel.get('confidence', 0)
                        )
            
            driver.close()
            print(f"Neo4j export complete: {len(entities)} entities, {len(relationships)} relationships")
            
        except ImportError:
            print("Neo4j driver not available. Install: pip install neo4j")
        except Exception as e:
            print(f"Neo4j export failed: {e}")