#!/bin/bash
# DELETE legacy files (they're in git history if you need them)

echo "⚠️  WARNING: This will DELETE the following files:"
echo "  - pipeline/ directory"
echo "  - Single_file.py"
echo "  - main.py"
echo "  - chatbot.py"
echo "  - fast_export.py, fast_batch_import.py, importer.py, simple_import.py"
echo "  - data_preprocessor.py"
echo "  - config.yaml"
echo ""
echo "These files are in git history if you need them later."
echo ""
read -p "Are you sure you want to DELETE these files? (yes/no): " confirm

if [ "$confirm" = "yes" ]; then
    echo "Deleting legacy files..."
    rm -rf pipeline/
    rm -f Single_file.py main.py chatbot.py
    rm -f fast_export.py fast_batch_import.py importer.py simple_import.py
    rm -f data_preprocessor.py config.yaml
    echo "✅ Legacy files deleted!"
else
    echo "❌ Cancelled. No files deleted."
fi
