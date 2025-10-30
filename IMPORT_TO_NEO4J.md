# Import CSV Files to Neo4j - Quick Guide

Your pipeline created CSV files with entities and relationships. Now let's import them to Neo4j!

## 📁 Your Generated Files

After running the pipeline, you have:

```
data/output/entities/entities_TIMESTAMP.csv        (3.6M entities)
data/output/relationships/relationships_TIMESTAMP.csv  (40.5M relationships)
```

## 🚀 Quick Import (3 Steps)

### Step 1: Start Neo4j

If you haven't already, start Neo4j in Docker:

```bash
docker run -d \
  --name neo4j-kg \
  -p 7474:7474 \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/myPassword123 \
  -e NEO4J_dbms_memory_heap_max__size=4G \
  -e NEO4J_dbms_memory_pagecache_size=2G \
  neo4j:5.13.0
```

**Verify it's running:**
```bash
docker ps | grep neo4j-kg
# Open browser: http://localhost:7474
# Login: neo4j / myPassword123
```

### Step 2: Find Your Latest CSV Files

```bash
# List your latest generated files
ls -lht data/output/entities/*.csv | head -1
ls -lht data/output/relationships/*.csv | head -1
```

### Step 3: Import to Neo4j

```bash
# Activate your virtual environment first
source venv/bin/activate

# Import with default settings (confidence >= 0.5)
python scripts/import_csv_to_neo4j.py \
  --entities data/output/entities/entities_20251029_191434.csv \
  --relationships data/output/relationships/relationships_20251029_191434.csv \
  --password myPassword123
```

**That's it!** The script will:
1. Clear existing data (optional)
2. Create constraints
3. Import entities in batches
4. Import relationships in batches
5. Show statistics

---

## ⚙️ Advanced Options

### Filter by Confidence

Only import high-confidence entities/relationships:

```bash
python scripts/import_csv_to_neo4j.py \
  --entities data/output/entities/entities_20251029_191434.csv \
  --relationships data/output/relationships/relationships_20251029_191434.csv \
  --password myPassword123 \
  --confidence 0.7
```

### Custom Batch Size

For systems with limited memory:

```bash
python scripts/import_csv_to_neo4j.py \
  --entities data/output/entities/entities_20251029_191434.csv \
  --relationships data/output/relationships/relationships_20251029_191434.csv \
  --password myPassword123 \
  --batch-size 1000
```

### Keep Existing Data

Don't clear the database before importing:

```bash
python scripts/import_csv_to_neo4j.py \
  --entities data/output/entities/entities_20251029_191434.csv \
  --relationships data/output/relationships/relationships_20251029_191434.csv \
  --password myPassword123 \
  --no-clear
```

### Custom Neo4j Connection

```bash
python scripts/import_csv_to_neo4j.py \
  --entities data/output/entities/entities_20251029_191434.csv \
  --relationships data/output/relationships/relationships_20251029_191434.csv \
  --uri bolt://production-server:7687 \
  --username neo4j \
  --password production_password \
  --confidence 0.8
```

---

## 📊 Expected Import Times

For your dataset (3.6M entities, 40.5M relationships):

- **With confidence >= 0.5**: ~15-30 minutes
- **With confidence >= 0.7**: ~5-10 minutes (fewer records)
- **High-end system**: ~5-10 minutes
- **Low-end system**: ~30-60 minutes

**Performance tips:**
- Use SSD for Neo4j data directory
- Increase batch size (--batch-size 10000) if you have lots of RAM
- Filter by confidence to reduce dataset size

---

## 🔍 Query Your Graph

After import, open Neo4j Browser (http://localhost:7474) and try these queries:

### View Sample Nodes
```cypher
MATCH (n:Entity)
RETURN n
LIMIT 50
```

### View Relationships
```cypher
MATCH (a:Entity)-[r:RELATED]->(b:Entity)
RETURN a.text, r.type, b.text
LIMIT 100
```

### Find Entities by Type
```cypher
MATCH (n:Entity)
WHERE n.label = 'NOUN_PHRASE'
RETURN n.text, n.confidence
ORDER BY n.confidence DESC
LIMIT 20
```

### Search for Specific Entities
```cypher
MATCH (n:Entity)
WHERE n.text CONTAINS 'procurement'
RETURN n.text, n.label, n.confidence
LIMIT 50
```

### Find Most Connected Entities
```cypher
MATCH (n:Entity)-[r:RELATED]->()
WITH n, count(r) as connections
RETURN n.text, n.label, connections
ORDER BY connections DESC
LIMIT 20
```

### Find Relationship Patterns
```cypher
MATCH path = (a:Entity)-[r1:RELATED]->(b:Entity)-[r2:RELATED]->(c:Entity)
WHERE a.text CONTAINS 'contract'
RETURN a.text, r1.type, b.text, r2.type, c.text
LIMIT 25
```

### Filter by Confidence
```cypher
MATCH (a:Entity)-[r:RELATED]->(b:Entity)
WHERE r.confidence > 0.8
RETURN a.text, r.type, b.text, r.confidence
ORDER BY r.confidence DESC
LIMIT 50
```

---

## 🛠️ Troubleshooting

### "Connection refused"
Neo4j is not running. Start it:
```bash
docker start neo4j-kg
```

### "Memory error" or "Out of memory"
Reduce batch size:
```bash
python scripts/import_csv_to_neo4j.py \
  --entities data/output/entities/entities_20251029_191434.csv \
  --relationships data/output/relationships/relationships_20251029_191434.csv \
  --password myPassword123 \
  --batch-size 1000 \
  --confidence 0.7
```

### Import is too slow
1. Use higher confidence threshold (imports fewer records)
2. Increase batch size if you have RAM
3. Use SSD for Neo4j storage
4. Give Neo4j more memory:
```bash
docker stop neo4j-kg
docker rm neo4j-kg
docker run -d \
  --name neo4j-kg \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/myPassword123 \
  -e NEO4J_dbms_memory_heap_max__size=8G \
  neo4j:5.13.0
```

### "Authentication failed"
Check your password matches:
```bash
# In the docker run command: -e NEO4J_AUTH=neo4j/YOUR_PASSWORD
# In the import command: --password YOUR_PASSWORD
```

---

## 📋 Full Example Workflow

```bash
# 1. Start Neo4j
docker run -d \
  --name neo4j-kg \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/myPassword123 \
  neo4j:5.13.0

# 2. Wait for Neo4j to be ready (~30 seconds)
sleep 30

# 3. Activate virtual environment
source venv/bin/activate

# 4. Import data (use your actual filenames)
python scripts/import_csv_to_neo4j.py \
  --entities data/output/entities/entities_20251029_191434.csv \
  --relationships data/output/relationships/relationships_20251029_191434.csv \
  --password myPassword123 \
  --confidence 0.6

# 5. Open Neo4j Browser
# Visit: http://localhost:7474
# Login: neo4j / myPassword123

# 6. Run a query
# In Neo4j Browser:
# MATCH (n:Entity) RETURN n LIMIT 50
```

---

## 🎯 Summary

**Your CSV files location:**
```
data/output/entities/entities_TIMESTAMP.csv
data/output/relationships/relationships_TIMESTAMP.csv
```

**Quick import command:**
```bash
python scripts/import_csv_to_neo4j.py \
  --entities data/output/entities/entities_TIMESTAMP.csv \
  --relationships data/output/relationships/relationships_TIMESTAMP.csv \
  --password YOUR_NEO4J_PASSWORD
```

**Then view at:** http://localhost:7474

That's it! Your knowledge graph is now in Neo4j! 🎉
