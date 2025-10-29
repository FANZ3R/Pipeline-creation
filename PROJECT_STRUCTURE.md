# Knowledge Graph Extraction Pipeline - Automated ML Project

## Project Structure

```
Pipeline-creation/
│
├── src/                          # Source code
│   ├── __init__.py
│   ├── data/                     # Data processing modules
│   │   ├── __init__.py
│   │   ├── ingestion.py          # Multi-format data ingestion
│   │   ├── converter.py          # Format conversion to JSON
│   │   └── validator.py          # Data quality validation
│   │
│   ├── extraction/               # Knowledge graph extraction
│   │   ├── __init__.py
│   │   ├── entity_extractor.py   # Entity extraction logic
│   │   ├── relationship_extractor.py  # Relationship discovery
│   │   └── kg_builder.py         # Main KG construction
│   │
│   ├── storage/                  # Data persistence
│   │   ├── __init__.py
│   │   ├── file_saver.py         # JSON/CSV export
│   │   └── neo4j_connector.py    # Neo4j database operations
│   │
│   └── pipeline/                 # Pipeline orchestration
│       ├── __init__.py
│       ├── orchestrator.py       # Main pipeline coordinator
│       └── monitoring.py         # Progress tracking & logging
│
├── config/                       # Configuration files
│   ├── default.yaml              # Default configuration
│   ├── development.yaml          # Development settings
│   └── production.yaml           # Production settings
│
├── data/                         # Data directories
│   ├── raw/                      # Original input files (any format)
│   ├── processed/                # Converted JSON files
│   └── output/                   # Extraction results
│       ├── entities/
│       ├── relationships/
│       └── reports/
│
├── logs/                         # Application logs
│
├── scripts/                      # Utility scripts
│   ├── run_pipeline.py           # Main execution script
│   ├── convert_data.py           # Standalone data converter
│   └── export_to_neo4j.py        # Neo4j export utility
│
├── requirements.txt              # Python dependencies
├── setup.py                      # Package setup
├── README.md                     # Project documentation
└── .env.example                  # Environment variables template
```

## Automated Workflow

### Stage 1: Data Ingestion & Conversion
- **Input**: Any format (Excel, JSON, CSV, PDF, DOCX, TXT)
- **Process**: Automatic format detection → JSON conversion
- **Output**: Standardized JSON in `data/processed/`
- **Validation**: Data quality checks, deduplication

### Stage 2: Knowledge Graph Extraction
- **Input**: JSON files from `data/processed/`
- **Process**:
  - Entity extraction (spaCy NER, noun phrases, tokens)
  - Relationship discovery (5 methods: verb-based, preposition, dependency, pattern, semantic)
  - Confidence scoring and deduplication
- **Output**: Entities & relationships

### Stage 3: Storage & Export
- **Formats**: JSON (detailed), CSV (tabular), Neo4j (graph database)
- **Location**: `data/output/`
- **Reports**: Statistics, entity distributions, relationship types

### Stage 4: Monitoring & Logging
- **Progress tracking**: Real-time batch processing updates
- **Error handling**: Graceful failure recovery
- **Metrics**: Extraction statistics, performance benchmarks

## Key Features

1. **Fully Automated**: Single command execution
2. **Format Agnostic**: Handles all common data formats
3. **Scalable**: Batch processing with configurable sizes
4. **Modular**: Clean separation of concerns
5. **Configurable**: YAML-based configuration
6. **Observable**: Comprehensive logging and monitoring
7. **Reproducible**: State preservation and checkpointing
