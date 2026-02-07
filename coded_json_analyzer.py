"""
Script to extract creativity metrics from coded story JSON files.

This script scans a folder for *_coded.json files, extracts creativity metrics,
quality flags, and repetition checks, then outputs the results to both JSON and CSV formats.
"""

import json
import csv
import os
from pathlib import Path
from typing import List, Dict, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_coded_json_files(folder_path: str) -> List[Path]:
    """
    Find all files matching the pattern *_coded.json in the specified folder.
    
    Args:
        folder_path: Path to the folder containing coded JSON files
        
    Returns:
        List of Path objects for matching files
    """
    folder = Path(folder_path)
    if not folder.exists():
        logger.error(f"Folder does not exist: {folder_path}")
        return []
    
    coded_files = list(folder.glob("*_coded.json"))
    logger.info(f"Found {len(coded_files)} coded JSON files")
    return coded_files


def extract_metrics_from_file(file_path: Path) -> Dict[str, Any]:
    """
    Extract creativity metrics, quality flags, and repetition checks from a single JSON file.
    
    Args:
        file_path: Path to the coded JSON file
        
    Returns:
        Dictionary containing extracted metrics, or None if extraction fails
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        # Extract required fields
        extracted_data = {
            'transcript_id': data.get('transcript_id', 'unknown'),
            'file_name': file_path.name,
            
            # Creativity metrics
            'fluency': data.get('creativity_metrics', {}).get('fluency', None),
            'flexibility': data.get('creativity_metrics', {}).get('flexibility', None),
            'elaboration_total': data.get('creativity_metrics', {}).get('elaboration_total', None),
            'elaboration_density': data.get('creativity_metrics', {}).get('elaboration_density', None),
            'categories_used': ', '.join(data.get('creativity_metrics', {}).get('categories_used', [])),
            
            # Quality flags
            'unclear_audio': data.get('quality_flags', {}).get('unclear_audio', None),
            'very_short_story': data.get('quality_flags', {}).get('very_short_story', None),
            'very_long_story': data.get('quality_flags', {}).get('very_long_story', None),
            'unusual_structure': data.get('quality_flags', {}).get('unusual_structure', None),
            'quality_notes': data.get('quality_flags', {}).get('notes', ''),
            
            # Repetition check
            'descriptors_in_stage_1_count': len(data.get('repetition_check', {}).get('descriptors_in_stage_1', [])),
            'descriptors_repeated_in_stage_2_count': len(data.get('repetition_check', {}).get('descriptors_repeated_in_stage_2', [])),
            'new_elaborations_in_stage_2': ', '.join(data.get('repetition_check', {}).get('new_elaborations_in_stage_2', [])),
            'new_elaborations_count': len(data.get('repetition_check', {}).get('new_elaborations_in_stage_2', []))
        }
        
        logger.info(f"Successfully extracted metrics from {file_path.name}")
        return extracted_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON in {file_path.name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error processing {file_path.name}: {e}")
        return None


def collect_all_metrics(folder_path: str) -> List[Dict[str, Any]]:
    """
    Collect metrics from all coded JSON files in the specified folder.
    
    Args:
        folder_path: Path to the folder containing coded JSON files
        
    Returns:
        List of dictionaries containing metrics from each file
    """
    coded_files = find_coded_json_files(folder_path)
    all_metrics = []
    
    for file_path in coded_files:
        metrics = extract_metrics_from_file(file_path)
        if metrics is not None:
            all_metrics.append(metrics)
    
    logger.info(f"Successfully processed {len(all_metrics)} out of {len(coded_files)} files")
    return all_metrics


def save_to_json(data: List[Dict[str, Any]], output_path: str) -> None:
    """
    Save collected metrics to a JSON file.
    
    Args:
        data: List of metric dictionaries
        output_path: Path where the JSON file should be saved
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        logger.info(f"Saved JSON summary to {output_path}")
    except Exception as e:
        logger.error(f"Failed to save JSON file: {e}")


def save_to_csv(data: List[Dict[str, Any]], output_path: str) -> None:
    """
    Save collected metrics to a CSV file.
    
    Args:
        data: List of metric dictionaries
        output_path: Path where the CSV file should be saved
    """
    if not data:
        logger.warning("No data to save to CSV")
        return
    
    try:
        # Get all keys from the first dictionary (assuming all have same structure)
        fieldnames = list(data[0].keys())
        
        with open(output_path, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        logger.info(f"Saved CSV summary to {output_path}")
    except Exception as e:
        logger.error(f"Failed to save CSV file: {e}")


def main():
    """
    Main function to orchestrate the metric extraction process.
    """
    # Configuration
    input_folder = "../data/coded/llm_outputs"
    output_json_path = "../data/coded/creativity_metrics_summary.json"
    output_csv_path = "../data/coded/creativity_metrics_summary.csv"
    
    logger.info("Starting creativity metrics extraction")
    logger.info(f"Input folder: {input_folder}")
    
    # Collect metrics from all files
    all_metrics = collect_all_metrics(input_folder)
    
    if not all_metrics:
        logger.warning("No metrics collected. Exiting.")
        return
    
    # Save to JSON and CSV
    save_to_json(all_metrics, output_json_path)
    save_to_csv(all_metrics, output_csv_path)
    
    logger.info("Metrics extraction complete")
    logger.info(f"Total files processed: {len(all_metrics)}")


if __name__ == "__main__":
    main()