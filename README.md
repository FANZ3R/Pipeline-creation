# Knowledge Graph Extraction Pipeline

An automated, production-ready ML pipeline for extracting knowledge graphs from multi-format documents using advanced NLP techniques.

## Features

- **Multi-Format Support**: Automatically processes JSON, CSV, Excel, PDF, DOCX, and TXT files
- **Automated Workflow**: Complete end-to-end pipeline from data ingestion to graph export
- **Advanced NLP**: Uses spaCy with 5 relationship discovery methods
- **Quality Assurance**: Built-in data validation, cleaning, and deduplication
- **Flexible Storage**: Exports to JSON, CSV, and Neo4j graph database
- **Monitoring & Logging**: Comprehensive progress tracking and performance metrics
- **Configuration-Driven**: YAML-based configuration for easy customization

## Project Structure

```
Pipeline-creation/
├── src/                          # Source code
│   ├── data/                     # Data processing modules
│   │   ├── ingestion.py          # Multi-format data loader
│   │   ├── converter.py          # JSON conversion
│   │   └── validator.py          # Data quality validation
│   ├── extraction/               # Knowledge graph extraction
│   │   ├── entity_extractor.py   # Entity extraction
│   │   ├── relationship_extractor.py  # Relationship discovery
│   │   └── kg_builder.py         # Main KG constructor
│   ├── storage/                  # Data persistence
│   │   ├── file_saver.py         # File export (JSON/CSV)
│   │   └── neo4j_connector.py    # Neo4j database export
│   └── pipeline/                 # Pipeline orchestration
│       ├── orchestrator.py       # Main coordinator
│       └── monitoring.py         # Progress tracking
├── config/                       # Configuration files
│   └── default.yaml              # Default settings
├── data/                         # Data directories
│   ├── raw/                      # Input files (any format)
│   ├── processed/                # Converted JSON files
│   └── output/                   # Extraction results
├── scripts/                      # Utility scripts
│   └── run_pipeline.py           # Main execution script
├── requirements.txt              # Python dependencies
├── setup.py                      # Package setup
└── README.md                     # This file
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Step 1: Clone or download the project

```bash
cd Pipeline-creation
```

### Step 2: Create a virtual environment (recommended)

```bash
python -m venv venv

# On Linux/Mac
source venv/bin/activate

# On Windows
venv\Scripts\activate
```

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Download spaCy language model

```bash
python -m spacy download en_core_web_sm
```

### Optional: Neo4j Setup

If you want to export to Neo4j:

1. Install Neo4j Desktop or Docker
2. Create a database
3. Note the connection URI, username, and password
4. Update `config/default.yaml` with your Neo4j credentials

## Quick Start

### 1. Add Your Data

Place your data files in the `data/raw/` directory. Supported formats:
- JSON (.json)
- CSV (.csv)
- Excel (.xlsx, .xls)
- PDF (.pdf)
- Word (.docx)
- Text (.txt)

Example:
```bash
cp your_data.xlsx data/raw/
cp your_documents.pdf data/raw/
```

### 2. Run the Pipeline

```bash
python scripts/run_pipeline.py
```

That's it! The pipeline will:
1. Load all data from `data/raw/`
2. Convert to standardized JSON format
3. Validate and clean the data
4. Extract entities and relationships
5. Save results to `data/output/`

### 3. View Results

Results are saved in multiple formats:
- **JSON**: `data/output/entities/` and `data/output/relationships/`
- **CSV**: Same directories, for easy analysis in Excel or Pandas
- **Reports**: `data/output/reports/` contains extraction statistics

## Usage

### Basic Usage

```bash
# Run with default configuration
python scripts/run_pipeline.py
```

### Advanced Usage

```bash
# Run with custom configuration
python scripts/run_pipeline.py --config config/custom.yaml

# Use environment variables for sensitive data
export NEO4J_PASSWORD=your_password
python scripts/run_pipeline.py
```

### Configuration

Edit `config/default.yaml` to customize:

```yaml
# Data ingestion settings
ingestion:
  min_text_length: 10

# Knowledge graph extraction
extraction:
  spacy_model: "en_core_web_sm"
  batch_size: 50

# Neo4j export (optional)
neo4j:
  enabled: false
  uri: "bolt://localhost:7687"
  username: "neo4j"
  password: "password"

# Output settings
output:
  base_dir: "data/output"
  formats:
    - json
    - csv
```

## How It Works

### Pipeline Workflow

```
1. Data Ingestion
   └─> Load files from data/raw/
   └─> Auto-detect formats (Excel, JSON, CSV, PDF, etc.)
   └─> Extract text blocks with metadata

2. Data Conversion
   └─> Convert all formats to standardized JSON
   └─> Save to data/processed/

3. Data Validation
   └─> Validate text quality (length, alpha ratio)
   └─> Clean text (remove URLs, emails)
   └─> Deduplicate blocks
   └─> Filter by quality score

4. Knowledge Graph Extraction
   └─> Entity Extraction (3 methods)
       ├─> spaCy NER
       ├─> Noun phrases
       └─> Single tokens (nouns, proper nouns)
   └─> Relationship Discovery (5 methods)
       ├─> Verb-based
       ├─> Preposition-based
       ├─> Dependency path analysis
       ├─> Syntactic patterns
       └─> Semantic proximity
   └─> Merge duplicates & calculate confidence

5. Storage
   └─> Save entities to JSON/CSV
   └─> Save relationships to JSON/CSV
   └─> Generate statistics report
   └─> Optional: Export to Neo4j

6. Monitoring
   └─> Track stage durations
   └─> Log metrics and errors
   └─> Generate summary report
```

### Entity Extraction Methods

1. **spaCy NER**: Recognizes named entities (people, organizations, locations, dates)
2. **Noun Phrases**: Captures multi-word entities like "machine learning algorithm"
3. **Single Tokens**: Extracts significant nouns and proper nouns

### Relationship Discovery Methods

1. **Verb-Based**: Finds entities connected by verbs (e.g., "Company develops Product")
2. **Preposition-Based**: Discovers relationships through prepositions (e.g., "City in Country")
3. **Dependency Paths**: Analyzes syntactic dependency trees
4. **Syntactic Patterns**: Matches patterns like Entity-Verb-Entity
5. **Semantic Proximity**: Finds entities close together in text

## Examples

### Example 1: Processing Procurement Data

```bash
# 1. Add Excel files to data/raw/
cp ProcureAbility.xlsx data/raw/
cp Glossary_Procurement.xlsx data/raw/

# 2. Run pipeline
python scripts/run_pipeline.py

# 3. View results
cat data/output/reports/summary_*.txt
```

### Example 2: Custom Configuration

Create `config/production.yaml`:

```yaml
ingestion:
  min_text_length: 20

extraction:
  batch_size: 100
  spacy_model: "en_core_web_lg"  # Larger model for better accuracy

neo4j:
  enabled: true
  uri: "bolt://production-server:7687"
  username: "neo4j"
  password: "${NEO4J_PASSWORD}"  # Use environment variable
```

Run:
```bash
export NEO4J_PASSWORD=secret
python scripts/run_pipeline.py --config config/production.yaml
```

## Output Format

### Entities JSON

```json
{
  "id": "ent_0",
  "text": "Machine Learning",
  "label": "NOUN_PHRASE",
  "confidence": 0.7,
  "source": "noun_chunk",
  "block_id": "block_0"
}
```

### Relationships JSON

```json
{
  "id": "rel_0",
  "subject": {"id": "ent_0", "text": "Company"},
  "discovered_type": "develops",
  "object": {"id": "ent_1", "text": "Product"},
  "confidence": 0.85,
  "sources": ["verb_discovery"],
  "sentence": "Company develops innovative Product."
}
```

### Entities CSV

| id | text | label | confidence | source | block_id |
|----|------|-------|------------|--------|----------|
| ent_0 | Machine Learning | NOUN_PHRASE | 0.7 | noun_chunk | block_0 |

### Relationships CSV

| id | subject_text | discovered_type | object_text | confidence | sources |
|----|--------------|-----------------|-------------|------------|---------|
| rel_0 | Company | develops | Product | 0.85 | verb_discovery |

## Performance

Typical performance on a modern laptop:
- **Data Ingestion**: ~1,000 blocks/second
- **KG Extraction**: ~5-10 blocks/second (depends on text length)
- **Neo4j Export**: ~1,000 entities/second, ~500 relationships/second

For a dataset with 1,000 text blocks:
- Total time: ~3-5 minutes
- Entities extracted: ~50,000-100,000
- Relationships extracted: ~200,000-500,000

## Troubleshooting

### Issue: spaCy model not found

```bash
# Download the model
python -m spacy download en_core_web_sm
```

### Issue: Neo4j connection failed

1. Check that Neo4j is running
2. Verify connection settings in `config/default.yaml`
3. Test connection:
   ```python
   from neo4j import GraphDatabase
   driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
   with driver.session() as session:
       result = session.run("RETURN 1")
       print(result.single())
   ```

### Issue: Out of memory

Reduce batch size in `config/default.yaml`:
```yaml
extraction:
  batch_size: 10  # Smaller batches use less memory
```

### Issue: No data files found

Ensure your data files are in `data/raw/` and have supported extensions:
```bash
ls -la data/raw/
```

## Advanced Features

### Custom spaCy Model

Use a larger, more accurate model:
```yaml
extraction:
  spacy_model: "en_core_web_lg"  # Or en_core_web_trf for transformer-based
```

### Confidence Thresholds

Filter low-confidence extractions:
```yaml
neo4j:
  confidence_threshold: 0.7  # Only export entities/relationships with confidence >= 0.7
```

### Batch Processing

For large datasets, process in batches:
```yaml
pipeline:
  json_batch_size: 5000  # Split into files of 5000 blocks each

extraction:
  batch_size: 100  # Process 100 blocks at a time
```

## API Usage

You can also use the pipeline programmatically:

```python
from src.pipeline import PipelineOrchestrator

# Initialize
orchestrator = PipelineOrchestrator(config_path="config/default.yaml")
orchestrator.initialize_components()

# Run pipeline
result = orchestrator.run()

# Access results
print(f"Extracted {len(result['entities'])} entities")
print(f"Extracted {len(result['relationships'])} relationships")
```

## Contributing

This project is structured for easy extension:

1. **Add new data loaders**: Edit `src/data/ingestion.py`
2. **Add new extraction methods**: Edit `src/extraction/relationship_extractor.py`
3. **Add new storage backends**: Create new module in `src/storage/`

## License

This project is provided as-is for educational and research purposes.

## Support

For issues, questions, or contributions:
1. Check the troubleshooting section
2. Review logs in `logs/pipeline.log`
3. Examine output reports in `data/output/reports/`

## Acknowledgments

- Built with [spaCy](https://spacy.io/) for NLP processing
- Uses [Neo4j](https://neo4j.com/) for graph database storage
- Based on research in knowledge graph extraction and relationship mining
