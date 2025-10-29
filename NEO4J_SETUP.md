# Neo4j Setup Guide for Knowledge Graph Pipeline

## Current Status
✅ .env file created with default Neo4j settings
✅ config/default.yaml has Neo4j disabled (safe to run without it)

## Option 1: Run WITHOUT Neo4j (Start Here)

The pipeline works perfectly without Neo4j - it saves to JSON/CSV:

```bash
./setup_project.sh
source venv/bin/activate
cp your_data.xlsx data/raw/
python scripts/run_pipeline.py
```

Results saved to: data/output/

## Option 2: Add Neo4j Later

### Step 1: Install Docker
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
# Then log out and log back in
```

### Step 2: Create Neo4j Container
```bash
docker run -d \
  --name neo4j-kg \
  -p 7474:7474 \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/myPassword123 \
  -v neo4j_data:/data \
  neo4j:5.13.0
```

### Step 3: Verify Neo4j is Running
```bash
# Check container status
docker ps | grep neo4j-kg

# View logs
docker logs neo4j-kg

# Access web interface
# Open browser: http://localhost:7474
# Login: neo4j / myPassword123
```

### Step 4: Update .env File
Edit .env and confirm these values:
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=myPassword123
```

### Step 5: Enable Neo4j in config/default.yaml
Change line 53 from:
```yaml
  enabled: false
```
To:
```yaml
  enabled: true
```

### Step 6: Run Pipeline with Neo4j
```bash
python scripts/run_pipeline.py
```

Now your knowledge graph will be exported to Neo4j!

### Step 7: View in Neo4j Browser
1. Open: http://localhost:7474
2. Login: neo4j / myPassword123
3. Run queries:

```cypher
// See all entities
MATCH (n:Entity) RETURN n LIMIT 50

// See all relationships
MATCH (a)-[r:RELATED]->(b)
RETURN a.text, r.type, b.text
LIMIT 50

// Search for specific entities
MATCH (n:Entity)
WHERE n.text CONTAINS 'procurement'
RETURN n
LIMIT 25
```

## Useful Docker Commands

```bash
# Stop Neo4j
docker stop neo4j-kg

# Start Neo4j
docker start neo4j-kg

# Restart Neo4j
docker restart neo4j-kg

# View logs
docker logs neo4j-kg -f

# Remove Neo4j (WARNING: deletes data)
docker rm -f neo4j-kg
docker volume rm neo4j_data
```

## Summary

1. **Now**: Run pipeline without Neo4j (works great!)
2. **Later**: Install Docker → Create Neo4j → Enable in config
3. **Enjoy**: Visualize your knowledge graph in Neo4j Browser!

