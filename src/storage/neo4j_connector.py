"""
Neo4j Connector Module
Handles exporting knowledge graphs to Neo4j database
"""

import logging
from typing import List, Dict, Any, Optional
from tqdm import tqdm

logger = logging.getLogger(__name__)


class Neo4jConnector:
    """
    Manages connection and data export to Neo4j graph database
    """

    def __init__(self, uri: str, username: str, password: str, config: Dict = None):
        """
        Initialize Neo4jConnector

        Args:
            uri: Neo4j connection URI (e.g., bolt://localhost:7687)
            username: Neo4j username
            password: Neo4j password
            config: Optional configuration dictionary
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.config = config or {}
        self.driver = None
        self.logger = logger

        self.confidence_threshold = self.config.get('confidence_threshold', 0.5)
        self.entity_batch_size = self.config.get('entity_batch_size', 1000)
        self.relationship_batch_size = self.config.get('relationship_batch_size', 500)
        self.clear_on_import = self.config.get('clear_database', True)

    def connect(self):
        """Establish connection to Neo4j"""
        try:
            from neo4j import GraphDatabase
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            # Test connection
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()
            self.logger.info(f"Successfully connected to Neo4j at {self.uri}")
            return True
        except ImportError:
            self.logger.error("neo4j package not installed. Install with: pip install neo4j")
            return False
        except Exception as e:
            self.logger.error(f"Failed to connect to Neo4j: {e}")
            return False

    def disconnect(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
            self.logger.info("Disconnected from Neo4j")

    def export_knowledge_graph(self, entities: List[Dict[str, Any]],
                               relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Export entities and relationships to Neo4j

        Args:
            entities: List of entity dictionaries
            relationships: List of relationship dictionaries

        Returns:
            Statistics dictionary
        """
        if not self.driver:
            if not self.connect():
                raise ConnectionError("Failed to connect to Neo4j")

        try:
            with self.driver.session() as session:
                # Clear database if configured
                if self.clear_on_import:
                    self.logger.info("Clearing existing data...")
                    session.run("MATCH (n) DETACH DELETE n")

                # Create constraints
                self._create_constraints(session)

                # Filter by confidence
                filtered_entities = [e for e in entities if e.get('confidence', 0) >= self.confidence_threshold]
                filtered_relationships = [r for r in relationships if r.get('confidence', 0) >= self.confidence_threshold]

                self.logger.info(f"Filtered to {len(filtered_entities)} entities and {len(filtered_relationships)} relationships")

                # Create entities
                entity_map = self._create_entities(session, filtered_entities)

                # Create relationships
                relationship_count = self._create_relationships(session, filtered_relationships, entity_map)

                # Get statistics
                stats = self._get_statistics(session)
                stats['entities_imported'] = len(entity_map)
                stats['relationships_imported'] = relationship_count

                self.logger.info(f"Successfully exported to Neo4j: {stats}")
                return stats

        except Exception as e:
            self.logger.error(f"Error exporting to Neo4j: {e}")
            raise

    def _create_constraints(self, session):
        """Create database constraints"""
        try:
            session.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE")
            self.logger.info("Created constraints")
        except Exception as e:
            self.logger.warning(f"Constraint creation warning: {e}")

    def _create_entities(self, session, entities: List[Dict[str, Any]]) -> Dict[str, Dict]:
        """Create entity nodes in batches"""
        self.logger.info("Creating entity nodes...")
        entity_map = {}

        # Process in batches
        total_batches = (len(entities) + self.entity_batch_size - 1) // self.entity_batch_size

        for batch_idx in tqdm(range(total_batches), desc="Creating entities"):
            start_idx = batch_idx * self.entity_batch_size
            end_idx = min(start_idx + self.entity_batch_size, len(entities))
            batch = entities[start_idx:end_idx]

            # Create batch query
            query = """
            UNWIND $entities AS entity
            CREATE (e:Entity {
                id: entity.id,
                text: entity.text,
                label: entity.label,
                confidence: entity.confidence,
                source: entity.source,
                block_id: entity.block_id,
                lemma: entity.lemma
            })
            RETURN e.id as id
            """

            # Prepare batch data
            batch_data = []
            for ent in batch:
                batch_data.append({
                    'id': ent['id'],
                    'text': ent['text'],
                    'label': ent['label'],
                    'confidence': ent['confidence'],
                    'source': ent['source'],
                    'block_id': ent.get('block_id', 'unknown'),
                    'lemma': ent.get('lemma', '')
                })

            # Execute batch
            result = session.run(query, entities=batch_data)
            for record in result:
                entity_id = record['id']
                entity_map[entity_id] = next(e for e in batch if e['id'] == entity_id)

        self.logger.info(f"Created {len(entity_map)} entity nodes")
        return entity_map

    def _create_relationships(self, session, relationships: List[Dict[str, Any]],
                             entity_map: Dict[str, Dict]) -> int:
        """Create relationship edges in batches"""
        self.logger.info("Creating relationships...")
        created_count = 0

        # Process in batches
        total_batches = (len(relationships) + self.relationship_batch_size - 1) // self.relationship_batch_size

        for batch_idx in tqdm(range(total_batches), desc="Creating relationships"):
            start_idx = batch_idx * self.relationship_batch_size
            end_idx = min(start_idx + self.relationship_batch_size, len(relationships))
            batch = relationships[start_idx:end_idx]

            # Filter batch for valid entities
            valid_batch = []
            for rel in batch:
                subject_id = rel.get('subject', {}).get('id')
                object_id = rel.get('object', {}).get('id')

                if subject_id in entity_map and object_id in entity_map:
                    valid_batch.append({
                        'subject_id': subject_id,
                        'object_id': object_id,
                        'type': rel.get('discovered_type', 'RELATED').upper().replace(' ', '_').replace('-', '_'),
                        'confidence': rel.get('confidence', 0),
                        'sources': ', '.join(rel.get('sources', [])),
                        'block_id': rel.get('block_id', 'unknown')
                    })

            if not valid_batch:
                continue

            # Create batch query
            query = """
            UNWIND $relationships AS rel
            MATCH (s:Entity {id: rel.subject_id})
            MATCH (o:Entity {id: rel.object_id})
            CREATE (s)-[r:RELATED {
                type: rel.type,
                confidence: rel.confidence,
                sources: rel.sources,
                block_id: rel.block_id
            }]->(o)
            """

            session.run(query, relationships=valid_batch)
            created_count += len(valid_batch)

        self.logger.info(f"Created {created_count} relationships")
        return created_count

    def _get_statistics(self, session) -> Dict[str, Any]:
        """Get database statistics"""
        stats = {}

        # Total nodes
        result = session.run("MATCH (n) RETURN count(n) as count")
        stats['total_nodes'] = result.single()['count']

        # Total relationships
        result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
        stats['total_relationships'] = result.single()['count']

        # Entity types distribution
        result = session.run("MATCH (n:Entity) RETURN n.label as type, count(*) as count ORDER BY count DESC LIMIT 20")
        stats['entity_types'] = result.data()

        return stats

    def test_connection(self) -> bool:
        """Test Neo4j connection"""
        try:
            if not self.driver:
                if not self.connect():
                    return False

            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()

            self.logger.info("Neo4j connection test successful")
            return True

        except Exception as e:
            self.logger.error(f"Neo4j connection test failed: {e}")
            return False

    def clear_database(self):
        """Clear all data from Neo4j"""
        if not self.driver:
            if not self.connect():
                raise ConnectionError("Failed to connect to Neo4j")

        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            self.logger.info("Cleared Neo4j database")

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
