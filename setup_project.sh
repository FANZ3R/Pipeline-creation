#!/bin/bash
# Setup script for Knowledge Graph Extraction Pipeline

echo "=========================================="
echo "Knowledge Graph Extraction Pipeline Setup"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "ERROR: Python 3.8 or higher is required. Found: Python $python_version"
    exit 1
fi
echo "✓ Python $python_version found"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Download spaCy model
echo "Downloading spaCy language model..."
python -m spacy download en_core_web_sm
echo "✓ spaCy model downloaded"
echo ""

# Create directory structure
echo "Creating directory structure..."
mkdir -p data/raw data/processed data/output logs
echo "✓ Directories created"
echo ""

# Copy environment template
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✓ Created .env file from template"
    echo "  (Edit .env to configure Neo4j credentials)"
else
    echo "✓ .env file already exists"
fi
echo ""

echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Add your data files to data/raw/"
echo "2. (Optional) Edit config/default.yaml"
echo "3. (Optional) Edit .env for Neo4j settings"
echo "4. Run the pipeline:"
echo "   source venv/bin/activate"
echo "   python scripts/run_pipeline.py"
echo ""
