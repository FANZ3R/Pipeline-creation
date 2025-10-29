# QUICKSTART GUIDE

Get started with the Knowledge Graph Extraction Pipeline in under 5 minutes!

## Prerequisites

- Python 3.8 or higher
- pip package manager

## Installation (5 steps)

### Step 1: Run the setup script

```bash
./setup_project.sh
```

This will:
- Create a virtual environment
- Install all dependencies
- Download the spaCy language model
- Create necessary directories

### Step 2: Activate the virtual environment

```bash
source venv/bin/activate
```

### Step 3: Add your data files

Copy any of these file types to `data/raw/`:
- Excel files (.xlsx, .xls)
- JSON files (.json)
- CSV files (.csv)
- PDF documents (.pdf)
- Word documents (.docx)
- Text files (.txt)

Example:
```bash
cp ~/Downloads/my_data.xlsx data/raw/
cp ~/Documents/*.pdf data/raw/
```

### Step 4: Run the pipeline

```bash
python scripts/run_pipeline.py
```

### Step 5: View results

Results are saved in `data/output/`:

```bash
# View summary
cat data/output/reports/summary_*.txt

# View entities (CSV)
head data/output/entities/entities_*.csv

# View relationships (CSV)
head data/output/relationships/relationships_*.csv
```

## What Just Happened?

The pipeline automatically:

1. **Loaded** all your data files from `data/raw/`
2. **Converted** them to a standardized JSON format
3. **Validated** and cleaned the text
4. **Extracted** entities (people, organizations, concepts)
5. **Discovered** relationships between entities
6. **Saved** everything to `data/output/` in multiple formats

## Example Output

After running on procurement documents, you'll get:

**Entities extracted:**
- Organizations: "Procurement Department", "Supply Chain"
- Concepts: "contract management", "vendor selection"
- Proper nouns: "RFP", "PO"

**Relationships discovered:**
- "Procurement Department" → manages → "vendor selection"
- "Supply Chain" → uses → "contract management"
- "RFP" → leads_to → "PO"

## Customization

### Change settings

Edit `config/default.yaml`:

```yaml
extraction:
  batch_size: 50  # Process 50 blocks at a time

validation:
  min_quality_score: 0.5  # Higher = stricter quality filtering
```

### Enable Neo4j export

1. Start Neo4j (Desktop or Docker)
2. Edit `config/default.yaml`:

```yaml
neo4j:
  enabled: true
  uri: "bolt://localhost:7687"
  username: "neo4j"
  password: "your_password"
```

3. Run pipeline again:

```bash
python scripts/run_pipeline.py
```

4. Open Neo4j Browser: http://localhost:7474

5. Query your graph:

```cypher
// View all entities
MATCH (n:Entity) RETURN n LIMIT 25

// View all relationships
MATCH (a)-[r:RELATED]->(b)
RETURN a.text, r.type, b.text
LIMIT 25

// Find specific entities
MATCH (n:Entity)
WHERE n.text CONTAINS 'procurement'
RETURN n
```

## What's Next?

### Analyze Results with Pandas

```python
import pandas as pd

# Load entities
entities = pd.read_csv('data/output/entities/entities_*.csv')
print(f"Total entities: {len(entities)}")
print(f"Entity types: {entities['label'].value_counts()}")

# Load relationships
relationships = pd.read_csv('data/output/relationships/relationships_*.csv')
print(f"Total relationships: {len(relationships)}")
print(f"Relationship types: {relationships['discovered_type'].value_counts()}")

# Find most connected entities
top_entities = relationships['subject_text'].value_counts().head(10)
print("Most connected entities:")
print(top_entities)
```

### Process More Data

Simply add more files to `data/raw/` and run again:

```bash
cp new_data/*.xlsx data/raw/
python scripts/run_pipeline.py
```

The pipeline will process everything automatically!

### Use Different spaCy Models

For better accuracy, use a larger model:

```bash
# Download larger model
python -m spacy download en_core_web_lg

# Update config/default.yaml
extraction:
  spacy_model: "en_core_web_lg"
```

## Troubleshooting

### Pipeline runs but no results?

Check that your files are in `data/raw/`:
```bash
ls -lh data/raw/
```

### Out of memory?

Reduce batch size in `config/default.yaml`:
```yaml
extraction:
  batch_size: 10  # Smaller batches
```

### Neo4j connection failed?

1. Verify Neo4j is running: http://localhost:7474
2. Check credentials in config
3. Test connection:
```bash
python -c "from neo4j import GraphDatabase; driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'password')); print('Connected!')"
```

## Performance Tips

For large datasets (1000+ documents):

1. **Use batch processing**:
```yaml
pipeline:
  json_batch_size: 5000
extraction:
  batch_size: 100
```

2. **Filter by quality**:
```yaml
validation:
  min_quality_score: 0.6  # Only keep high-quality text
```

3. **Use confidence thresholds**:
```yaml
neo4j:
  confidence_threshold: 0.7  # Only export high-confidence extractions
```

## Need Help?

1. Check `logs/pipeline.log` for detailed logs
2. Review `data/output/reports/` for extraction statistics
3. Read the full [README.md](README.md) for advanced usage

## That's It!

You now have a fully automated knowledge graph extraction pipeline. Happy extracting! 🚀
