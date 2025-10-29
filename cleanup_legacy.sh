#!/bin/bash
# Move legacy files to a legacy/ folder for reference

echo "Creating legacy folder..."
mkdir -p legacy

echo "Moving old pipeline files..."
mv pipeline/ legacy/
mv Single_file.py legacy/
mv main.py legacy/
mv chatbot.py legacy/
mv fast_export.py legacy/
mv fast_batch_import.py legacy/
mv importer.py legacy/
mv simple_import.py legacy/
mv data_preprocessor.py legacy/
mv config.yaml legacy/

echo "✅ Done! Legacy files moved to legacy/"
echo "The new automated pipeline uses only src/ directory"
ls -la legacy/
