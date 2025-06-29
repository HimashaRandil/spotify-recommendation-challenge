import json
import os

# Check if the temp file exists and what's in it
temp_file = "data/processed/enriched_artists.json.tmp"
original_file = "data/interim/unique_artists.json"

print(f"Temp file exists: {os.path.exists(temp_file)}")
print(f"Original file exists: {os.path.exists(original_file)}")

if os.path.exists(temp_file):
    try:
        with open(temp_file, "r", encoding="utf-8") as f:  # Add UTF-8 encoding
            temp_data = json.load(f)
        print(f"Artists in temp file: {len(temp_data.get('artists', []))}")
        print(
            f"Successfully enriched: {temp_data.get('metadata', {}).get('successfully_enriched', 'N/A')}"
        )
    except Exception as e:
        print(f"Error reading temp file: {e}")

if os.path.exists(original_file):
    try:
        with open(original_file, "r", encoding="utf-8") as f:  # Add UTF-8 encoding
            orig_data = json.load(f)
        print(f"Artists in original file: {len(orig_data.get('artists', []))}")
    except Exception as e:
        print(f"Error reading original file: {e}")
