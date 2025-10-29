"""
Unified Knowledge Graph Pipeline - Single File
Preserves exact logic from spacy_blocks_kg.ipynb with ingestion capability

Usage: python unified_kg_pipeline.py
"""

import json
import spacy
from collections import Counter, defaultdict
from itertools import combinations
import numpy as np
from tqdm import tqdm
import pandas as pd
from neo4j import GraphDatabase
import logging
from datetime import datetime
import pickle
import os
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kg_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# EXACT COPY FROM NOTEBOOK - NO CHANGES
# ============================================================================

class GeneralizedKnowledgeGraphExtractor:
    def __init__(self, nlp_model):
        self.nlp = nlp_model
        self.entity_id_counter = 0
        self.relationship_id_counter = 0
        
        # Store discovered relationship patterns
        self.discovered_patterns = defaultdict(list)
        self.relationship_templates = []
        
        print("Initialized GeneralizedKnowledgeGraphExtractor")
    
    def extract_entities(self, doc):
        """Extract entities using multiple methods"""
        entities = []
        seen_spans = set()
        
        # 1. Standard spaCy NER entities
        for ent in doc.ents:
            span_key = (ent.start, ent.end)
            if span_key not in seen_spans:
                entity = {
                    "id": f"ent_{self.entity_id_counter}",
                    "text": ent.text.strip(),
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "start_token": ent.start,
                    "end_token": ent.end,
                    "confidence": 1.0,
                    "source": "spacy_ner",
                    "lemma": ent.lemma_,
                    "root_dep": ent.root.dep_,
                    "root_pos": ent.root.pos_
                }
                entities.append(entity)
                seen_spans.add(span_key)
                self.entity_id_counter += 1
        
        # 2. Extract noun phrases as potential entities
        for np in doc.noun_chunks:
            span_key = (np.start, np.end)
            if span_key not in seen_spans and len(np.text.strip()) > 2:
                entity = {
                    "id": f"ent_{self.entity_id_counter}",
                    "text": np.text.strip(),
                    "label": "NOUN_PHRASE",
                    "start": np.start_char,
                    "end": np.end_char,
                    "start_token": np.start,
                    "end_token": np.end,
                    "confidence": 0.7,
                    "source": "noun_chunk",
                    "lemma": np.lemma_,
                    "root_dep": np.root.dep_,
                    "root_pos": np.root.pos_
                }
                entities.append(entity)
                seen_spans.add(span_key)
                self.entity_id_counter += 1
        
        # 3. Extract significant single tokens (nouns, proper nouns)
        for token in doc:
            if (token.pos_ in ["NOUN", "PROPN"] and 
                not token.is_stop and 
                not token.is_punct and 
                len(token.text) > 2):
                
                span_key = (token.i, token.i + 1)
                if span_key not in seen_spans:
                    entity = {
                        "id": f"ent_{self.entity_id_counter}",
                        "text": token.text,
                        "label": f"{token.pos_}",
                        "start": token.idx,
                        "end": token.idx + len(token.text),
                        "start_token": token.i,
                        "end_token": token.i + 1,
                        "confidence": 0.5,
                        "source": "single_token",
                        "lemma": token.lemma_,
                        "root_dep": token.dep_,
                        "root_pos": token.pos_
                    }
                    entities.append(entity)
                    seen_spans.add(span_key)
                    self.entity_id_counter += 1
        
        return entities
    
    def discover_verb_relationships(self, doc, entities):
        """Discover relationships based on verbs connecting entities"""
        relationships = []
        
        for token in doc:
            if token.pos_ == "VERB":
                verb = token
                
                # Find all entities connected to this verb through dependencies
                connected_entities = []
                
                # Look at all children and ancestors of the verb
                for child in verb.children:
                    entity = self._find_entity_for_token(child, entities)
                    if entity:
                        connected_entities.append({
                            "entity": entity,
                            "role": child.dep_,
                            "position": "child"
                        })
                
                # Check verb's head if it's an entity
                if verb.head != verb:
                    entity = self._find_entity_for_token(verb.head, entities)
                    if entity:
                        connected_entities.append({
                            "entity": entity,
                            "role": verb.dep_,
                            "position": "parent"
                        })
                
                # Create relationships between connected entities
                if len(connected_entities) >= 2:
                    # Generate all pairwise relationships
                    for i, conn1 in enumerate(connected_entities):
                        for conn2 in connected_entities[i+1:]:
                            relationship = {
                                "id": f"rel_{self.relationship_id_counter}",
                                "discovered_type": f"{verb.lemma_}",
                                "verb_text": verb.text,
                                "verb_lemma": verb.lemma_,
                                "subject": conn1["entity"],
                                "subject_role": conn1["role"],
                                "object": conn2["entity"],
                                "object_role": conn2["role"],
                                "confidence": self._calculate_confidence(verb, conn1, conn2),
                                "source": "verb_discovery",
                                "sentence": str(verb.sent),
                                "context_window": doc[max(0, verb.i-5):min(len(doc), verb.i+6)].text
                            }
                            relationships.append(relationship)
                            self.relationship_id_counter += 1
                            
                            # Store pattern for future learning
                            pattern_key = f"{conn1['role']}-{verb.lemma_}-{conn2['role']}"
                            self.discovered_patterns[pattern_key].append(relationship)
        
        return relationships
    
    def discover_preposition_relationships(self, doc, entities):
        """Discover relationships through prepositions"""
        relationships = []
        
        for token in doc:
            if token.pos_ == "ADP":  # ADP is the POS tag for prepositions
                prep = token
                
                # Find entities before and after the preposition
                before_entity = None
                after_entity = None
                
                # Look for entity that this preposition modifies (usually its head)
                if prep.head != prep:
                    before_entity = self._find_entity_for_token(prep.head, entities)
                
                # Look for entity that is the object of the preposition
                for child in prep.children:
                    if child.dep_ in ["pobj", "dobj", "obj"]:
                        after_entity = self._find_entity_for_token(child, entities)
                        break
                
                if before_entity and after_entity:
                    relationship = {
                        "id": f"rel_{self.relationship_id_counter}",
                        "discovered_type": f"{prep.text}_relation",
                        "preposition": prep.text,
                        "preposition_lemma": prep.lemma_,
                        "subject": before_entity,
                        "object": after_entity,
                        "confidence": 0.7,
                        "source": "preposition_discovery",
                        "sentence": str(prep.sent),
                        "context_window": doc[max(0, prep.i-5):min(len(doc), prep.i+6)].text
                    }
                    relationships.append(relationship)
                    self.relationship_id_counter += 1
        
        return relationships
    
    def discover_dependency_path_relationships(self, doc, entities):
        """Discover relationships by analyzing dependency paths between entities"""
        relationships = []
        
        # For each pair of entities in the same sentence
        for sent in doc.sents:
            sent_entities = [
                ent for ent in entities 
                if ent["start_token"] >= sent.start and ent["end_token"] <= sent.end
            ]
            
            for ent1, ent2 in combinations(sent_entities, 2):
                # Find the dependency path between entities
                path = self._find_dependency_path(doc, ent1, ent2)
                
                if path and len(path) > 0:
                    # Extract the relationship from the path
                    path_text = self._extract_path_text(doc, path)
                    path_pattern = self._extract_path_pattern(doc, path)
                    
                    relationship = {
                        "id": f"rel_{self.relationship_id_counter}",
                        "discovered_type": path_pattern,
                        "path_text": path_text,
                        "dependency_path": [doc[i].dep_ for i in path],
                        "subject": ent1,
                        "object": ent2,
                        "confidence": self._calculate_path_confidence(path),
                        "source": "dependency_path",
                        "sentence": str(sent),
                        "path_length": len(path)
                    }
                    relationships.append(relationship)
                    self.relationship_id_counter += 1
        
        return relationships
    
    def discover_pattern_based_relationships(self, doc, entities):
        """Discover relationships using syntactic patterns"""
        relationships = []
        
        # Pattern 1: Entity-Verb-Entity
        for i in range(len(doc) - 2):
            if (self._is_entity_token(doc[i], entities) and 
                doc[i+1].pos_ == "VERB" and 
                self._is_entity_token(doc[i+2], entities)):
                
                ent1 = self._find_entity_for_token(doc[i], entities)
                ent2 = self._find_entity_for_token(doc[i+2], entities)
                
                if ent1 and ent2:
                    relationship = {
                        "id": f"rel_{self.relationship_id_counter}",
                        "discovered_type": f"{doc[i+1].lemma_}_pattern",
                        "connecting_word": doc[i+1].text,
                        "connecting_lemma": doc[i+1].lemma_,
                        "subject": ent1,
                        "object": ent2,
                        "confidence": 0.6,
                        "source": "syntactic_pattern",
                        "pattern": "E-V-E",
                        "sentence": str(doc[i].sent)
                    }
                    relationships.append(relationship)
                    self.relationship_id_counter += 1
        
        # Pattern 2: Entity's Entity (possessive)
        for i in range(len(doc) - 2):
            if (self._is_entity_token(doc[i], entities) and 
                doc[i+1].text in ["'s", "'s", "of"] and 
                self._is_entity_token(doc[i+2], entities)):
                
                ent1 = self._find_entity_for_token(doc[i], entities)
                ent2 = self._find_entity_for_token(doc[i+2], entities)
                
                if ent1 and ent2:
                    relationship = {
                        "id": f"rel_{self.relationship_id_counter}",
                        "discovered_type": "possessive_relation",
                        "connecting_word": doc[i+1].text,
                        "subject": ent1,
                        "object": ent2,
                        "confidence": 0.7,
                        "source": "syntactic_pattern",
                        "pattern": "E-POSS-E",
                        "sentence": str(doc[i].sent)
                    }
                    relationships.append(relationship)
                    self.relationship_id_counter += 1
        
        return relationships
    
    def discover_semantic_relationships(self, doc, entities):
        """Discover relationships based on semantic similarity and context"""
        relationships = []
        
        # For entities that appear close to each other
        for sent in doc.sents:
            sent_entities = [
                ent for ent in entities 
                if ent["start_token"] >= sent.start and ent["end_token"] <= sent.end
            ]
            
            for ent1, ent2 in combinations(sent_entities, 2):
                # Calculate token distance
                distance = abs(ent1["start_token"] - ent2["start_token"])
                
                if distance <= 10:  # Within 10 tokens
                    # Find connecting words between entities
                    start = min(ent1["end_token"], ent2["end_token"])
                    end = max(ent1["start_token"], ent2["start_token"])
                    
                    if start < end:
                        connecting_tokens = doc[start:end]
                        connecting_text = " ".join([t.text for t in connecting_tokens])
                        
                        # Identify key connecting words (verbs, prepositions)
                        key_words = [t for t in connecting_tokens 
                                   if t.pos_ in ["VERB", "ADP", "CCONJ"]]
                        
                        if key_words:
                            relationship = {
                                "id": f"rel_{self.relationship_id_counter}",
                                "discovered_type": "_".join([w.lemma_ for w in key_words[:2]]),
                                "connecting_text": connecting_text,
                                "key_words": [w.lemma_ for w in key_words],
                                "subject": ent1,
                                "object": ent2,
                                "confidence": 0.5 / (1 + distance/10),
                                "source": "semantic_proximity",
                                "distance": distance,
                                "sentence": str(sent)
                            }
                            relationships.append(relationship)
                            self.relationship_id_counter += 1
        
        return relationships
    
    # Helper methods
    def _find_entity_for_token(self, token, entities):
        """Find entity that contains the given token"""
        for entity in entities:
            if entity["start_token"] <= token.i < entity["end_token"]:
                return entity
        return None
    
    def _is_entity_token(self, token, entities):
        """Check if token is part of an entity"""
        return self._find_entity_for_token(token, entities) is not None
    
    def _find_dependency_path(self, doc, ent1, ent2):
        """Find shortest dependency path between two entities"""
        # Get root tokens of entities
        token1 = doc[ent1["start_token"]]
        token2 = doc[ent2["start_token"]]
        
        # Simple BFS to find path
        visited = set()
        queue = [(token1, [token1.i])]
        
        while queue:
            current, path = queue.pop(0)
            
            if current == token2:
                return path
            
            if current in visited:
                continue
            
            visited.add(current)
            
            # Add head and children to queue
            if current.head != current and len(path) < 10:
                queue.append((current.head, path + [current.head.i]))
            
            for child in current.children:
                if len(path) < 10:
                    queue.append((child, path + [child.i]))
        
        return None
    
    def _extract_path_text(self, doc, path):
        """Extract text from dependency path"""
        if not path:
            return ""
        return " ".join([doc[i].text for i in path])
    
    def _extract_path_pattern(self, doc, path):
        """Extract pattern from dependency path"""
        if not path:
            return "unknown"
        
        # Create pattern from POS tags and key dependencies
        pattern_parts = []
        for i in path:
            token = doc[i]
            if token.pos_ in ["VERB", "ADP", "CCONJ"]:
                pattern_parts.append(token.lemma_)
        
        return "_".join(pattern_parts) if pattern_parts else "direct_connection"
    
    def _calculate_confidence(self, verb, conn1, conn2):
        """Calculate confidence score for verb-based relationships"""
        base_confidence = 0.5
        
        # Boost for certain dependency relations
        important_deps = ["nsubj", "dobj", "nsubjpass", "agent", "attr"]
        if conn1["role"] in important_deps:
            base_confidence += 0.15
        if conn2["role"] in important_deps:
            base_confidence += 0.15
        
        # Boost for active voice
        if verb.tag_ in ["VB", "VBZ", "VBP", "VBD"]:
            base_confidence += 0.1
        
        return min(base_confidence, 1.0)
    
    def _calculate_path_confidence(self, path):
        """Calculate confidence based on dependency path length"""
        if not path:
            return 0.1
        
        # Shorter paths are more confident
        length_penalty = len(path) / 10.0
        return max(0.3, 1.0 - length_penalty)
    
    def merge_duplicate_relationships(self, relationships):
        """Merge duplicate relationships and adjust confidence"""
        merged = {}
        
        for rel in relationships:
            # Create a key for grouping similar relationships
            key = (
                rel.get("subject", {}).get("id"),
                rel.get("object", {}).get("id"),
                rel.get("discovered_type", "unknown")
            )
            
            if key in merged:
                # Increase confidence when multiple methods find the same relationship
                merged[key]["confidence"] = min(
                    1.0, 
                    merged[key]["confidence"] + rel["confidence"] * 0.2
                )
                merged[key]["sources"].append(rel["source"])
            else:
                rel["sources"] = [rel["source"]]
                merged[key] = rel
        
        return list(merged.values())
    
    def extract_knowledge_graph(self, text):
        """Main method to extract complete knowledge graph"""
        doc = self.nlp(text)
        
        # Step 1: Extract entities
        entities = self.extract_entities(doc)
        
        # Step 2: Discover relationships using multiple methods
        verb_rels = self.discover_verb_relationships(doc, entities)
        prep_rels = self.discover_preposition_relationships(doc, entities)
        path_rels = self.discover_dependency_path_relationships(doc, entities)
        pattern_rels = self.discover_pattern_based_relationships(doc, entities)
        semantic_rels = self.discover_semantic_relationships(doc, entities)
        
        # Combine all relationships
        all_relationships = verb_rels + prep_rels + path_rels + pattern_rels + semantic_rels
        
        # Merge duplicates and boost confidence
        merged_relationships = self.merge_duplicate_relationships(all_relationships)
        
        # Generate statistics
        stats = {
            "total_entities": len(entities),
            "total_relationships": len(merged_relationships),
            "unique_relationship_types": len(set(r.get("discovered_type", "unknown") 
                                               for r in merged_relationships)),
            "entity_types": Counter(ent["label"] for ent in entities),
            "relationship_types": Counter(rel.get("discovered_type", "unknown") 
                                        for rel in merged_relationships),
            "discovery_methods": Counter(source 
                                       for rel in merged_relationships 
                                       for source in rel.get("sources", [])),
            "avg_confidence": {
                "entities": sum(e["confidence"] for e in entities) / len(entities) if entities else 0,
                "relationships": sum(r["confidence"] for r in merged_relationships) / len(merged_relationships) if merged_relationships else 0
            }
        }
        
        # Identify most common patterns
        pattern_frequency = Counter()
        for pattern_key, rels in self.discovered_patterns.items():
            pattern_frequency[pattern_key] = len(rels)
        
        return {
            "text": text,
            "entities": entities,
            "relationships": merged_relationships,
            "statistics": stats,
            "discovered_patterns": dict(pattern_frequency.most_common(10)),
            "linguistic_features": {
                "token_count": len(doc),
                "sentence_count": len(list(doc.sents)),
                "noun_chunks": len(list(doc.noun_chunks))
            }
        }


# ============================================================================
# INGESTION PIPELINE - NEW FUNCTIONALITY
# ============================================================================

# def load_text_from_file(filepath):
#     """Load text from various file formats"""
#     path = Path(filepath)
#     ext = path.suffix.lower()
    
#     try:
#         if ext == '.json':
#             with open(filepath, 'r', encoding='utf-8') as f:
#                 data = json.load(f)
            
#             # Extract text from JSON
#             if isinstance(data, list):
#                 return [{'text': str(item.get('text', item)), 'source': path.name} 
#                        for item in data if item]
#             else:
#                 return [{'text': str(data.get('text', data)), 'source': path.name}]
        
#         elif ext == '.txt':
#             with open(filepath, 'r', encoding='utf-8') as f:
#                 content = f.read()
#             paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 10]
#             return [{'text': p, 'source': path.name} for p in paragraphs]
        
#         elif ext == '.csv':
#             df = pd.read_csv(filepath)
#             # Find text columns
#             text_cols = [col for col in df.columns 
#                         if 'text' in col.lower() or 'content' in col.lower()]
#             if not text_cols:
#                 text_cols = [col for col in df.columns if df[col].dtype == 'object']
            
#             blocks = []
#             for _, row in df.iterrows():
#                 text = ' '.join(str(row[col]) for col in text_cols if pd.notna(row[col]))
#                 if len(text.strip()) > 10:
#                     blocks.append({'text': text, 'source': path.name})
#             return blocks
        
#         else:
#             # Try as plain text
#             with open(filepath, 'r', encoding='utf-8') as f:
#                 content = f.read()
#             return [{'text': content, 'source': path.name}]
            
#     except Exception as e:
#         logger.error(f"Failed to load {filepath}: {e}")
#         return []

def load_text_from_file(filepath):
    """Load text from various file formats"""
    path = Path(filepath)
    ext = path.suffix.lower()
    
    try:
        if ext == '.json':
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                return [{'text': str(item.get('text', item)), 'source': path.name} 
                       for item in data if item]
            else:
                return [{'text': str(data.get('text', data)), 'source': path.name}]
        
        elif ext == '.txt':
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 10]
            return [{'text': p, 'source': path.name} for p in paragraphs]
        
        elif ext == '.csv':
            df = pd.read_csv(filepath)
            text_cols = [col for col in df.columns 
                        if 'text' in col.lower() or 'content' in col.lower()]
            if not text_cols:
                text_cols = [col for col in df.columns if df[col].dtype == 'object']
            
            blocks = []
            for _, row in df.iterrows():
                text = ' '.join(str(row[col]) for col in text_cols if pd.notna(row[col]))
                if len(text.strip()) > 10:
                    blocks.append({'text': text, 'source': path.name})
            return blocks
        
        # ADD THIS EXCEL SECTION:
        elif ext in ['.xlsx', '.xls']:
            df = pd.read_excel(filepath)
            
            # Find text columns
            text_cols = [col for col in df.columns 
                        if 'text' in col.lower() or 'content' in col.lower()]
            if not text_cols:
                text_cols = [col for col in df.columns if df[col].dtype == 'object']
            
            blocks = []
            for idx, row in df.iterrows():
                text = ' '.join(str(row[col]) for col in text_cols if pd.notna(row[col]))
                if len(text.strip()) > 10:
                    blocks.append({
                        'text': text, 
                        'source': path.name,
                        'row': idx
                    })
            return blocks
        
        else:
            # Try as plain text
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return [{'text': content, 'source': path.name}]
            
    except Exception as e:
        logger.error(f"Failed to load {filepath}: {e}")
        return []


def load_all_from_directory(directory_path):
    """Load all text files from directory"""
    all_blocks = []
    directory = Path(directory_path)
    
    if not directory.exists():
        logger.error(f"Directory not found: {directory_path}")
        return []
    
    for file_path in directory.iterdir():
        if file_path.is_file():
            blocks = load_text_from_file(str(file_path))
            all_blocks.extend(blocks)
            logger.info(f"Loaded {len(blocks)} blocks from {file_path.name}")
    
    return all_blocks


def process_blocks(data, extractor, batch_size=50):
    """Process all blocks - EXACT LOGIC FROM NOTEBOOK"""
    all_entities = []
    all_relationships = []
    block_metadata = []
    
    logger.info(f"Processing {len(data)} blocks in batches of {batch_size}")
    
    for i in tqdm(range(0, len(data), batch_size), desc="Processing batches"):
        batch = data[i:i+batch_size]
        
        for block_idx, block in enumerate(batch):
            actual_idx = i + block_idx
            
            # Extract text from block
            if isinstance(block, dict):
                text = block.get('text', '')
            else:
                text = str(block)
            
            if not text or len(text.strip()) < 10:
                continue
            
            try:
                # Extract knowledge graph
                kg = extractor.extract_knowledge_graph(text)
                
                # Add block ID to entities and relationships
                for entity in kg['entities']:
                    entity['block_id'] = actual_idx
                    all_entities.append(entity)
                
                for rel in kg['relationships']:
                    rel['block_id'] = actual_idx
                    all_relationships.append(rel)
                
                # Store metadata
                block_metadata.append({
                    'block_id': actual_idx,
                    'statistics': kg['statistics'],
                    'discovered_patterns': kg['discovered_patterns']
                })
                
            except Exception as e:
                logger.error(f"Error processing block {actual_idx}: {str(e)}")
                continue
    
    logger.info(f"Extracted {len(all_entities)} entities and {len(all_relationships)} relationships")
    return all_entities, all_relationships, block_metadata


def save_to_files(entities, relationships, metadata, output_dir="kg_output"):
    """Save extracted data to files - EXACT LOGIC FROM NOTEBOOK"""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save entities to JSON
    entities_file = f"{output_dir}/entities_{timestamp}.json"
    with open(entities_file, 'w', encoding='utf-8') as f:
        json.dump(entities, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(entities)} entities to {entities_file}")
    
    # Save relationships to JSON
    relationships_file = f"{output_dir}/relationships_{timestamp}.json"
    with open(relationships_file, 'w', encoding='utf-8') as f:
        json.dump(relationships, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(relationships)} relationships to {relationships_file}")
    
    # Save metadata
    metadata_file = f"{output_dir}/metadata_{timestamp}.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved metadata to {metadata_file}")
    
    # Save entities to CSV
    entities_df = pd.DataFrame(entities)
    entities_csv = f"{output_dir}/entities_{timestamp}.csv"
    entities_df.to_csv(entities_csv, index=False, encoding='utf-8')
    logger.info(f"Saved entities to CSV: {entities_csv}")
    
    # Save simplified relationships to CSV
    relationships_simple = []
    for rel in relationships:
        relationships_simple.append({
            'id': rel.get('id'),
            'subject_text': rel.get('subject', {}).get('text', ''),
            'subject_id': rel.get('subject', {}).get('id', ''),
            'discovered_type': rel.get('discovered_type', 'unknown'),
            'object_text': rel.get('object', {}).get('text', ''),
            'object_id': rel.get('object', {}).get('id', ''),
            'confidence': rel.get('confidence', 0),
            'source': ', '.join(rel.get('sources', [])),
            'block_id': rel.get('block_id')
        })
    
    relationships_df = pd.DataFrame(relationships_simple)
    relationships_csv = f"{output_dir}/relationships_{timestamp}.csv"
    relationships_df.to_csv(relationships_csv, index=False, encoding='utf-8')
    logger.info(f"Saved relationships to CSV: {relationships_csv}")
    
    return entities_file, relationships_file, entities_csv, relationships_csv


def populate_neo4j(entities, relationships, neo4j_uri, neo4j_user, neo4j_password):
    """Populate Neo4j - EXACT LOGIC FROM NOTEBOOK"""
    logger.info("Starting Neo4j population...")
    
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    try:
        with driver.session() as session:
            # Clear existing data
            logger.info("Clearing existing data...")
            session.run("MATCH (n) DETACH DELETE n")
            
            # Create constraints
            try:
                session.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE")
            except Exception as e:
                logger.warning(f"Constraint creation failed: {e}")
            
            # Batch create entities
            logger.info("Creating entity nodes...")
            entity_map = {}
            
            for entity in tqdm(entities, desc="Creating entities"):
                query = """
                CREATE (e:Entity {
                    id: $id,
                    text: $text,
                    label: $label,
                    confidence: $confidence,
                    source: $source,
                    block_id: $block_id
                })
                RETURN e
                """
                result = session.run(query,
                    id=entity['id'],
                    text=entity['text'],
                    label=entity['label'],
                    confidence=entity['confidence'],
                    source=entity['source'],
                    block_id=entity.get('block_id', -1)
                )
                node = result.single()
                if node:
                    entity_map[entity['id']] = entity
            
            # Create relationships
            logger.info("Creating relationships...")
            for rel in tqdm(relationships, desc="Creating relationships"):
                subject_id = rel.get('subject', {}).get('id')
                object_id = rel.get('object', {}).get('id')
                
                if subject_id in entity_map and object_id in entity_map:
                    rel_type = rel.get('discovered_type', 'RELATED').upper().replace(' ', '_').replace('-', '_')
                    
                    query = """
                    MATCH (s:Entity {id: $subject_id})
                    MATCH (o:Entity {id: $object_id})
                    CREATE (s)-[r:RELATED {
                        type: $rel_type,
                        confidence: $confidence,
                        source: $source,
                        block_id: $block_id
                    }]->(o)
                    """
                    session.run(query,
                        subject_id=subject_id,
                        object_id=object_id,
                        rel_type=rel_type,
                        confidence=rel.get('confidence', 0),
                        source=', '.join(rel.get('sources', [])),
                        block_id=rel.get('block_id', -1)
                    )
            
            logger.info("Neo4j population complete!")
            
            # Get statistics
            stats = {}
            result = session.run("MATCH (n) RETURN count(n) as count")
            stats['total_nodes'] = result.single()['count']
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            stats['total_relationships'] = result.single()['count']
            
            result = session.run("MATCH (n:Entity) RETURN n.label as type, count(*) as count ORDER BY count DESC")
            stats['entity_types'] = result.data()
            
            logger.info(f"Neo4j Statistics: {stats}")
            return stats
            
    finally:
        driver.close()


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution - preserves notebook logic with ingestion capability"""
    
    print("=" * 60)
    print("UNIFIED KNOWLEDGE GRAPH PIPELINE")
    print("Exact logic from spacy_blocks_kg.ipynb")
    print("=" * 60)
    
    # Configuration
    INPUT_DIR = "data/input"
    OUTPUT_DIR = "kg_output"
    JSON_FILE = None  # Will auto-detect files in INPUT_DIR
    
    # Neo4j settings
    USE_NEO4J = True
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "your_secure_password"
    
    try:
        # Create directories
        os.makedirs(INPUT_DIR, exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Load spaCy model
        logger.info("Loading spaCy model...")
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.error("spaCy model not found. Run: python -m spacy download en_core_web_sm")
            return
        
        # Initialize extractor - EXACT CLASS FROM NOTEBOOK
        logger.info("Initializing Knowledge Graph Extractor...")
        extractor = GeneralizedKnowledgeGraphExtractor(nlp)
        
        # Load data from input directory
        logger.info(f"Loading data from {INPUT_DIR}...")
        text_blocks = load_all_from_directory(INPUT_DIR)
        
        if not text_blocks:
            logger.error(f"No data found in {INPUT_DIR}")
            logger.info("Add your data files (JSON, TXT, CSV) to the input directory")
            return
        
        logger.info(f"Loaded {len(text_blocks)} text blocks")
        
        # Process blocks - EXACT LOGIC FROM NOTEBOOK
        entities, relationships, metadata = process_blocks(text_blocks, extractor, batch_size=50)
        
        # Save to files - EXACT LOGIC FROM NOTEBOOK
        entities_json, relationships_json, entities_csv, relationships_csv = save_to_files(
            entities, relationships, metadata, OUTPUT_DIR
        )
        
        # Populate Neo4j if enabled
        if USE_NEO4J:
            logger.info("Connecting to Neo4j...")
            neo4j_stats = populate_neo4j(
                entities, relationships,
                NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
            )
        
        # Save extractor state
        with open(f'{OUTPUT_DIR}/extractor_state.pkl', 'wb') as f:
            pickle.dump({
                'entity_id_counter': extractor.entity_id_counter,
                'relationship_id_counter': extractor.relationship_id_counter,
                'discovered_patterns': dict(extractor.discovered_patterns)
            }, f)
        logger.info("Saved extractor state")
        
        # Final summary
        logger.info("=" * 60)
        logger.info("EXTRACTION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total entities extracted: {len(entities)}")
        logger.info(f"Total relationships extracted: {len(relationships)}")
        logger.info(f"Files saved in: {OUTPUT_DIR}/")
        
        if USE_NEO4J:
            logger.info(f"Neo4j nodes created: {neo4j_stats['total_nodes']}")
            logger.info(f"Neo4j relationships created: {neo4j_stats['total_relationships']}")
            logger.info("View in Neo4j Browser: http://localhost:7475")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise


if __name__ == "__main__":
    main()