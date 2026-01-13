"""
Simple masking: Replace speaker labels only
"""

import json
import re
from pathlib import Path

def mask_speaker_labels(text):
    """
    Replace ROBOT and EXPERIMENTER with generic PROMPT label
    Preserves all question content and interaction patterns
    """
    # Replace ROBOT: with PROMPT:
    text = re.sub(r'\bPEPPER\s+\[', 'PROMPT [', text)
    
    # Replace EXPERIMENTER: with PROMPT:
    text = re.sub(r'\bEXPERIMENTER\s+\[', 'PROMPT [', text)
    
    return text

def parse_transcript(filepath):
    """
    Parse transcript and separate Stage 1 and Stage 2
    Adjust this based on YOUR actual file format
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Example parsing - adjust to your format
    # Look for story continuation prompt
    markers = [
        'Stage 2',
        'Stage B',
        'What happened next?',
        'What do you think happened next?',
        'What do you think might happen?',
    ]
    
    for marker in markers:
        if marker.lower() in content.lower():
            # Find position of marker (case-insensitive)
            match = re.search(re.escape(marker), content, re.IGNORECASE)
            if match:
                split_pos = match.start()
                stage_1 = content[:split_pos]
                stage_2 = content[split_pos:]
                return stage_1.strip(), stage_2.strip()
    
    # If no marker found, return all as Stage 1
    print(f"No Stage 2 marker found in {filepath.name}")
    return content.strip(), ""

def main():
    # Setup paths
    raw_dir = Path('../data/raw/transcriptions')
    output_file = Path('data/processed/transcripts_prepared_masked.json')
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Check raw directory exists
    if not raw_dir.exists():
        print(f"Raw transcriptions directory not found: {raw_dir}")
        print(f"Please create it and add your transcript files")
        return
    
    transcripts = []
    errors = []
    
    # Statistics
    robot_count = 0
    experimenter_count = 0
    
    print(f"Processing transcripts from: {raw_dir}")
    print(f"{'='*60}\n")
    
    # Process each transcript file
    for file in sorted(raw_dir.glob('*.txt')):
        # Extract participant info from filename
        # Adjust based on your naming convention
        parts = file.stem.split('.')
        participant_id = parts[0]  # e.g., P01
        # age = parts[1] if len(parts) > 1 else 'Unknown'
        
        try:
            # 1. Parse into Stage 1 and Stage 2
            stage_1_raw, stage_2_raw = parse_transcript(file)
            
            if not stage_2_raw:
                print(f"⚠️  {participant_id}: No Stage 2 found, skipping")
                errors.append(f"{participant_id}: No Stage 2 content")
                continue
            
            # 3. Mask speaker labels
            stage_1_masked = mask_speaker_labels(stage_1_raw)
            stage_2_masked = mask_speaker_labels(stage_2_raw)
            
            # 4. Create transcript object
            transcript = {
                'participant_id': participant_id,
                'stage_1_context': stage_1_masked,
                'stage_2_story': stage_2_masked
            }
            
            transcripts.append(transcript)
            print(f"✓ {participant_id}")
            
        except Exception as e:
            error_msg = f"{participant_id}: {str(e)}"
            errors.append(error_msg)
            print(f"✗ {participant_id}: {e}")
    
    # Save masked transcripts
    if transcripts:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(transcripts, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print(f"\n{'='*60}")
    print("PROCESSING SUMMARY")
    print(f"{'='*60}")
    print(f"Files found: {len(list(raw_dir.glob('*.txt')))}")
    print(f"Successfully processed: {len(transcripts)}")
    print(f"Errors: {len(errors)}")
    
    if errors:
        print(f"\nErrors encountered:")
        for error in errors:
            print(f"  - {error}")
    
    # print(f"\n{'='*60}")
    # print("MASKING SUMMARY")
    # print(f"{'='*60}")
    # print(f"'ROBOT:' labels masked: {robot_count}")
    # print(f"'EXPERIMENTER:' labels masked: {experimenter_count}")
    # print(f"Total labels masked: {robot_count + experimenter_count}")
    
    # Verification
    print(f"\n{'='*60}")
    print("VERIFICATION")
    print(f"{'='*60}")
    
    issues = []
    for t in transcripts:
        full_text = t['stage_1_context'] + ' ' + t['stage_2_story']
        
        if 'ROBOT:' in full_text:
            issues.append(f"{t['transcript_id']}: ROBOT label still present")
        
        if 'EXPERIMENTER:' in full_text:
            issues.append(f"{t['transcript_id']}: EXPERIMENTER label still present")
    
    if issues:
        print("Issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✓ All labels successfully masked")
        print("✓ No 'ROBOT:' or 'EXPERIMENTER:' labels remain")
    
    # Final output location
    print(f"\n{'='*60}")
    print(f"✓ Output saved to: {output_file}")
    print(f"✓ Ready for LLM coding")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
