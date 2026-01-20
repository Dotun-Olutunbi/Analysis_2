"""
JSON to Dataset Merger & Validation Analysis
For Child-Robot Storytelling Creativity Study

This script:
1. Reads multiple JSON files (one per participant) from Claude API coding
2. Merges them into a single pandas DataFrame
3. Loads manual ELAN coding from Excel
4. Compares manual vs automated coding
5. Calculates agreement statistics (ICC, correlation, MAE)
6. Generates visualizations

Author: Dotun's Research Assistant
Date: January 2026
"""

import pandas as pd
import numpy as np
import json
import os
from pathlib import Path
from scipy.stats import pearsonr
from sklearn.metrics import mean_absolute_error
import matplotlib.pyplot as plt
import seaborn as sns

# Optional: for ICC calculation
try:
    import pingouin as pg
    PINGOUIN_AVAILABLE = True
except ImportError:
    PINGOUIN_AVAILABLE = False
    print("Warning: pingouin not installed. ICC calculation will be skipped.")
    print("Install with: pip install pingouin --break-system-packages")


# ============================================================================
# STEP 1: LOAD AND MERGE CLAUDE API JSON FILES
# ============================================================================

def load_claude_json_files(json_folder_path):
    """
    Load all JSON files from a folder and merge into single DataFrame.
    
    Parameters:
    -----------
    json_folder_path : str
        Path to folder containing JSON files (one per participant)
        
    Returns:
    --------
    pd.DataFrame with columns: ParticipantID, Fluency_Claude, Flexibility_Claude, 
                               Elaboration_Claude, ElabDensity_Claude
    
    Expected JSON structure:
    {
        "participant_id": "FRIAM02",
        "fluency": 5,
        "flexibility": 3,
        "elaboration": 1,
        "elaboration_density": 0.20,
        "categories_used": ["character", "action", "goal"],
        "story_elements": [...]
    }
    """
    
    json_files = list(Path(json_folder_path).glob("*_coded.json"))
    
    if not json_files:
        raise FileNotFoundError(f"No JSON files found in {json_folder_path}")
    
    print(f"Found {len(json_files)} JSON files to process")
    
    claude_data = []
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract relevant fields
            # Adjust field names based on your actual JSON structure
            participant_id = data.get('participant_id') or data.get('ParticipantID') or json_file.stem
            participant_id = participant_id.split('_')[0]  # Clean ID if needed
            
            # Extract creativity metrics (nested structure)
            creativity_metrics = data.get('creativity_metrics', {})
            
            record = {
                'ParticipantID': participant_id,
                'Fluency_Claude': creativity_metrics.get('fluency', np.nan),
                'Flexibility_Claude': creativity_metrics.get('flexibility', np.nan),
                'Elaboration_Claude': creativity_metrics.get('elaboration_total', np.nan),
                'ElabDensity_Claude': creativity_metrics.get('elaboration_density', np.nan),
                'Categories_Claude': ','.join(creativity_metrics.get('categories_used', [])) if isinstance(creativity_metrics.get('categories_used'), list) else creativity_metrics.get('categories_used', '')
            }
            
            claude_data.append(record)
            print(f"  ✓ Loaded: {participant_id}")
            
        except Exception as e:
            print(f"  ✗ Error loading {json_file.name}: {e}")
            continue
    
    claude_df = pd.DataFrame(claude_data)
    
    print(f"\nSuccessfully loaded {len(claude_df)} participant records")
    return claude_df


# ============================================================================
# STEP 2: LOAD MANUAL ELAN CODING FROM EXCEL
# ============================================================================

def load_manual_coding(excel_file_path):
    """
    Load manual ELAN coding results from Excel file.
    
    Parameters:
    -----------
    excel_file_path : str
        Path to Excel file with manual coding
        
    Returns:
    --------
    pd.DataFrame with columns: ParticipantID, Fluency_Manual, Flexibility_Manual,
                               Elaboration_Manual, ElabDensity_Manual
    
    Expected Excel structure:
    ParticipantID | Fluency | Flexibility | Elaboration | ElabDensity | ...
    FRIAM02      | 5       | 3           | 1           | 0.20        | ...
    """
    
    manual_df = pd.read_excel(excel_file_path)
    
    # Rename columns to have _Manual suffix
    rename_dict = {
        'Fluency': 'Fluency_Manual',
        'Flexibility': 'Flexibility_Manual',
        'Elaboration': 'Elaboration_Manual',
        'ElabDensity': 'Elaboration_Density_Manual'
    }
    
    manual_df = manual_df.rename(columns=rename_dict)
    
    # Keep only necessary columns
    keep_cols = ['ParticipantID', 'Fluency_Manual', 'Flexibility_Manual', 
                 'Elaboration_Manual', 'Elaboration_Density_Manual']
    
    # Add any other columns that exist
    optional_cols = ['Age', 'Gender', 'Condition', 'Categories_Used']
    for col in optional_cols:
        if col in manual_df.columns:
            keep_cols.append(col)
    
    manual_df = manual_df[keep_cols]
    
    print(f"Loaded manual coding for {len(manual_df)} participants")
    return manual_df


# ============================================================================
# STEP 3: MERGE DATASETS
# ============================================================================

def merge_datasets(manual_df, claude_df):
    """
    Merge manual and Claude coding datasets on ParticipantID.
    
    Returns merged DataFrame with both manual and automated scores.
    """
    
    merged_df = manual_df.merge(claude_df, on='ParticipantID', how='inner')
    
    print(f"\nMerged dataset: {len(merged_df)} participants")
    
    # Check for mismatches
    manual_only = set(manual_df['ParticipantID']) - set(claude_df['ParticipantID'])
    claude_only = set(claude_df['ParticipantID']) - set(manual_df['ParticipantID'])
    
    if manual_only:
        print(f"  ⚠ Warning: {len(manual_only)} participants in manual but not Claude: {manual_only}")
    if claude_only:
        print(f"  ⚠ Warning: {len(claude_only)} participants in Claude but not manual: {claude_only}")
    
    return merged_df


# ============================================================================
# STEP 4: CALCULATE AGREEMENT STATISTICS
# ============================================================================

def calculate_agreement_statistics(merged_df):
    """
    Calculate Pearson correlation, ICC, and MAE for each metric.
    
    Returns dictionary with all statistics.
    """
    
    metrics = ['Fluency', 'Flexibility', 'Elaboration']
    results = {}
    
    print("\n" + "="*70)
    print("AGREEMENT STATISTICS")
    print("="*70)
    
    for metric in metrics:
        manual_col = f'{metric}_Manual'
        claude_col = f'{metric}_Claude'
        
        # Remove any NaN values
        valid_data = merged_df[[manual_col, claude_col]].dropna()
        
        if len(valid_data) == 0:
            print(f"\n{metric}: No valid data")
            continue
        
        manual_vals = valid_data[manual_col]
        claude_vals = valid_data[claude_col]
        
        # Pearson correlation
        corr, p_value = pearsonr(manual_vals, claude_vals)
        
        # Mean Absolute Error
        mae = mean_absolute_error(manual_vals, claude_vals)
        
        # Mean difference
        mean_diff = (manual_vals - claude_vals).mean()
        
        # Standard deviation of differences
        std_diff = (manual_vals - claude_vals).std()
        
        results[metric] = {
            'correlation': corr,
            'p_value': p_value,
            'mae': mae,
            'mean_difference': mean_diff,
            'std_difference': std_diff,
            'n': len(valid_data)
        }
        
        # Print results
        print(f"\n{metric}:")
        print(f"  Pearson r = {corr:.3f} (p = {p_value:.4f})")
        print(f"  MAE = {mae:.2f}")
        print(f"  Mean difference (Manual - Claude) = {mean_diff:.2f} ± {std_diff:.2f}")
        print(f"  n = {len(valid_data)} participants")
        
        # Interpretation
        if corr >= 0.90:
            print(f"  → Excellent agreement")
        elif corr >= 0.80:
            print(f"  → Good agreement")
        elif corr >= 0.70:
            print(f"  → Acceptable agreement")
        else:
            print(f"  → Poor agreement")
    
    # Calculate ICC if pingouin is available
    if PINGOUIN_AVAILABLE:
        print("\n" + "-"*70)
        print("Intraclass Correlation Coefficients (ICC)")
        print("-"*70)
        
        for metric in metrics:
            try:
                icc_result = calculate_icc(merged_df, metric)
                results[metric]['icc'] = icc_result
                print(f"\n{metric} ICC(2,1) = {icc_result:.3f}")
                
                if icc_result >= 0.90:
                    print(f"  → Excellent reliability")
                elif icc_result >= 0.75:
                    print(f"  → Good reliability")
                elif icc_result >= 0.50:
                    print(f"  → Moderate reliability")
                else:
                    print(f"  → Poor reliability")
                    
            except Exception as e:
                print(f"\n{metric}: Could not calculate ICC - {e}")
    
    return results


def calculate_icc(df, metric):
    """
    Calculate ICC(2,1) - two-way random effects, absolute agreement, single rater.
    
    This is the appropriate ICC for comparing two measurement methods.
    """
    
    # Reshape data to long format for ICC calculation
    manual_col = f'{metric}_Manual'
    claude_col = f'{metric}_Claude'
    
    # Create long format
    data_long = pd.DataFrame({
        'ParticipantID': list(df['ParticipantID']) + list(df['ParticipantID']),
        'Rater': ['Manual']*len(df) + ['Claude']*len(df),
        'Score': list(df[manual_col]) + list(df[claude_col])
    })
    
    # Remove NaN
    data_long = data_long.dropna()
    
    # Calculate ICC
    icc_result = pg.intraclass_corr(
        data=data_long,
        targets='ParticipantID',
        raters='Rater',
        ratings='Score'
    )
    
    # Extract ICC(2,1) - two-way random, absolute agreement, single rater
    icc_value = icc_result[icc_result['Type'] == 'ICC2']['ICC'].values[0]
    
    return icc_value


# ============================================================================
# STEP 5: IDENTIFY AND ANALYZE DISCREPANCIES
# ============================================================================

def analyze_discrepancies(merged_df, threshold=2):
    """
    Identify cases where manual and Claude coding differ substantially.
    
    Parameters:
    -----------
    threshold : int
        Difference threshold for flagging discrepancies
    """
    
    print("\n" + "="*70)
    print(f"DISCREPANCY ANALYSIS (threshold = {threshold})")
    print("="*70)
    
    metrics = ['Fluency', 'Flexibility', 'Elaboration']
    
    for metric in metrics:
        manual_col = f'{metric}_Manual'
        claude_col = f'{metric}_Claude'
        
        merged_df[f'{metric}_Diff'] = merged_df[manual_col] - merged_df[claude_col]
        merged_df[f'{metric}_AbsDiff'] = abs(merged_df[f'{metric}_Diff'])
        
        # Find large discrepancies
        discrepancies = merged_df[merged_df[f'{metric}_AbsDiff'] >= threshold]
        
        if len(discrepancies) > 0:
            print(f"\n{metric}: {len(discrepancies)} cases with |difference| ≥ {threshold}")
            print(discrepancies[['ParticipantID', manual_col, claude_col, f'{metric}_Diff']].to_string(index=False))
        else:
            print(f"\n{metric}: No large discrepancies")
    
    return merged_df


# ============================================================================
# STEP 6: CREATE VISUALIZATIONS
# ============================================================================

def create_visualizations(merged_df, output_folder='validation_plots'):
    """
    Create comparison plots: scatter plots and Bland-Altman plots.
    """
    
    os.makedirs(output_folder, exist_ok=True)
    
    metrics = ['Fluency', 'Flexibility', 'Elaboration']
    
    for metric in metrics:
        manual_col = f'{metric}_Manual'
        claude_col = f'{metric}_Claude'
        
        # Remove NaN
        plot_data = merged_df[[manual_col, claude_col, 'ParticipantID']].dropna()
        
        if len(plot_data) == 0:
            continue
        
        # 1. Scatter plot with line of perfect agreement
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Scatter plot
        ax1.scatter(plot_data[manual_col], plot_data[claude_col], alpha=0.6, s=100)
        
        # Add participant ID labels to points
        for idx, row in plot_data.iterrows():
            ax1.annotate(row['ParticipantID'], 
                        (row[manual_col], row[claude_col]),
                        xytext=(5, 5), 
                        textcoords='offset points',
                        fontsize=8,
                        alpha=0.7)
        
        # Line of perfect agreement
        min_val = min(plot_data[manual_col].min(), plot_data[claude_col].min())
        max_val = max(plot_data[manual_col].max(), plot_data[claude_col].max())
        ax1.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='Perfect Agreement')
        
        # Calculate correlation for title
        corr, _ = pearsonr(plot_data[manual_col], plot_data[claude_col])
        
        ax1.set_xlabel('Manual Coding (ELAN)', fontsize=12)
        ax1.set_ylabel('Claude API Coding', fontsize=12)
        ax1.set_title(f'{metric}: Manual vs Automated\nr = {corr:.3f}, n = {len(plot_data)}', fontsize=14)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. Bland-Altman plot
        plot_data['Mean'] = (plot_data[manual_col] + plot_data[claude_col]) / 2
        plot_data['Diff'] = plot_data[manual_col] - plot_data[claude_col]
        
        mean_diff = plot_data['Diff'].mean()
        std_diff = plot_data['Diff'].std()
        
        ax2.scatter(plot_data['Mean'], plot_data['Diff'], alpha=0.6, s=100)
        
        # Add participant ID labels to Bland-Altman points
        for idx, row in plot_data.iterrows():
            ax2.annotate(row['ParticipantID'], 
                        (row['Mean'], row['Diff']),
                        xytext=(5, 5), 
                        textcoords='offset points',
                        fontsize=8,
                        alpha=0.7)
        ax2.axhline(y=0, color='k', linestyle='--', linewidth=1, label='Zero Difference')
        ax2.axhline(y=mean_diff, color='b', linestyle='-', linewidth=2, label=f'Mean Diff = {mean_diff:.2f}')
        ax2.axhline(y=mean_diff + 1.96*std_diff, color='r', linestyle='--', linewidth=1, label='±1.96 SD')
        ax2.axhline(y=mean_diff - 1.96*std_diff, color='r', linestyle='--', linewidth=1)
        
        ax2.set_xlabel('Average Score [(Manual + Claude) / 2]', fontsize=12)
        ax2.set_ylabel('Difference (Manual - Claude)', fontsize=12)
        ax2.set_title(f'{metric}: Bland-Altman Plot\nMean Diff = {mean_diff:.2f} ± {std_diff:.2f}', fontsize=14)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        output_path = os.path.join(output_folder, f'{metric}_comparison.png')
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"  ✓ Saved: {output_path}")
        plt.close()
    
    print(f"\nAll plots saved to {output_folder}/")


# ============================================================================
# STEP 7: GENERATE SUMMARY REPORT
# ============================================================================

def generate_summary_report(merged_df, results, output_file='validation_report.txt'):
    """
    Generate a text summary report of validation results.
    """
    
    with open(output_file, 'w') as f:
        f.write("="*70 + "\n")
        f.write("VALIDATION REPORT: Manual vs Automated Coding\n")
        f.write("Child-Robot Storytelling Creativity Study\n")
        f.write("="*70 + "\n\n")
        
        f.write(f"Sample Size: {len(merged_df)} participants\n\n")
        
        f.write("-"*70 + "\n")
        f.write("AGREEMENT STATISTICS\n")
        f.write("-"*70 + "\n\n")
        
        for metric, stats in results.items():
            f.write(f"{metric}:\n")
            f.write(f"  Pearson correlation: r = {stats['correlation']:.3f} (p = {stats['p_value']:.4f})\n")
            
            if 'icc' in stats:
                f.write(f"  ICC(2,1): {stats['icc']:.3f}\n")
            
            f.write(f"  Mean Absolute Error: {stats['mae']:.2f}\n")
            f.write(f"  Mean Difference: {stats['mean_difference']:.2f} ± {stats['std_difference']:.2f}\n")
            f.write(f"  Sample size: n = {stats['n']}\n\n")
        
        f.write("-"*70 + "\n")
        f.write("INTERPRETATION\n")
        f.write("-"*70 + "\n\n")
        
        # Overall assessment
        avg_corr = np.mean([results[m]['correlation'] for m in results.keys()])
        avg_mae = np.mean([results[m]['mae'] for m in results.keys()])
        
        if avg_corr >= 0.85 and avg_mae < 1.5:
            f.write("CONCLUSION: Excellent agreement between manual and automated coding.\n")
            f.write("Recommendation: Automated system is appropriate for coding remaining transcripts.\n")
        elif avg_corr >= 0.70 and avg_mae < 2.5:
            f.write("CONCLUSION: Good to moderate agreement between manual and automated coding.\n")
            f.write("Recommendation: Consider using automated system with manual review of flagged cases.\n")
        else:
            f.write("CONCLUSION: Poor agreement between manual and automated coding.\n")
            f.write("Recommendation: Manual coding required for all transcripts, or refine automated system.\n")
    
    print(f"\n✓ Summary report saved to {output_file}")


# ============================================================================
# MAIN EXECUTION FUNCTION
# ============================================================================

def main():
    """
    Main execution function - run the complete validation analysis.
    """
    
    print("\n" + "="*70)
    print("VALIDATION ANALYSIS: Manual ELAN vs Claude API Coding")
    print("="*70 + "\n")
    
    # ========================================================================
    # CONFIGURATION - EDIT THESE PATHS
    # ========================================================================
    
    # Path to folder containing Claude API JSON files
    JSON_FOLDER = "../data/coded/llm_outputs"
    
    # Path to Excel file with manual ELAN coding
    MANUAL_EXCEL = "../data/coded/Elan_manual_coding.xlsx"
    
    # Output folder for plots and reports
    OUTPUT_FOLDER = "../data/coded/validation_output"
    
    # ========================================================================
    
    try:
        # Step 1: Load Claude JSON files
        print("STEP 1: Loading Claude API JSON files...")
        claude_df = load_claude_json_files(JSON_FOLDER)
        
        # Step 2: Load manual ELAN coding
        print("\nSTEP 2: Loading manual ELAN coding...")
        manual_df = load_manual_coding(MANUAL_EXCEL)
        
        # Step 3: Merge datasets
        print("\nSTEP 3: Merging datasets...")
        merged_df = merge_datasets(manual_df, claude_df)
        
        # Save merged dataset
        merged_output = os.path.join(OUTPUT_FOLDER, "merged_comparison.csv")
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
        merged_df.to_csv(merged_output, index=False)
        print(f"  ✓ Merged dataset saved to {merged_output}")
        
        # Step 4: Calculate agreement statistics
        print("\nSTEP 4: Calculating agreement statistics...")
        results = calculate_agreement_statistics(merged_df)
        
        # Step 5: Analyze discrepancies
        print("\nSTEP 5: Analyzing discrepancies...")
        merged_df = analyze_discrepancies(merged_df, threshold=2)
        
        # Create visualizations
        print("\nSTEP 6: Creating visualizations...")
        plot_folder = os.path.join(OUTPUT_FOLDER, "plots")
        create_visualizations(merged_df, output_folder=plot_folder)
        
        # Step 7: Generate summary report
        print("\nSTEP 7: Generating summary report...")
        report_file = os.path.join(OUTPUT_FOLDER, "validation_report.txt")
        generate_summary_report(merged_df, results, output_file=report_file)
        
        print("\n" + "="*70)
        print("VALIDATION ANALYSIS COMPLETE!")
        print("="*70)
        print(f"\nAll outputs saved to: {OUTPUT_FOLDER}")
        print("  - merged_comparison.csv (combined dataset)")
        print("  - validation_report.txt (summary statistics)")
        print(f"  - plots/ (comparison visualizations)")
        
    except Exception as e:
        print(f"\n✗ Error during analysis: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# HELPER FUNCTION: Quick Statistics Without Full Analysis
# ============================================================================

def quick_stats(manual_excel, json_folder):
    """
    Quick function to just print statistics without generating all outputs.
    """
    
    claude_df = load_claude_json_files(json_folder)
    manual_df = load_manual_coding(manual_excel)
    merged_df = merge_datasets(manual_df, claude_df)
    results = calculate_agreement_statistics(merged_df)
    
    return merged_df, results


# ============================================================================
# RUN THE SCRIPT
# ============================================================================

if __name__ == "__main__":
    main()
    
    # Alternatively, for quick stats only:
    # merged_df, results = quick_stats(
    #     manual_excel="/path/to/manual.xlsx",
    #     json_folder="/path/to/json_files"
    # )