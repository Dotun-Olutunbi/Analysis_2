"""
2_run_llm_coding.py
Send masked transcripts to Claude API for story element coding
Uses Document 2 v3.1 prompt with blind coding protocol
"""

import json
import os
import time
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def load_system_prompt():
    """Load Document 2 v3.1 prompt as system message"""
    # Adjust this path to where you saved Document 2 v3.1
    prompt_path = Path('../prompts/stage2_prompt.md')
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()

def code_transcript_with_claude(client, system_prompt, transcript):
    """
    Send one transcript to Claude API for coding
    Returns: (coded_data, error_message)
    """
    
    # Prepare the user message with Stage 1 and Stage 2
    user_message = f"""Please code this transcript according to the instructions.

Stage 1 Context (for reference only, do not code):
{transcript['stage_1_context']}

Stage 2 Story (CODE THIS):
{transcript['stage_2_story']}

Remember:
- Use Stage 1 to understand context and resolve pronouns
- Check Stage 1 for repeated descriptors (don't count as new elaborations)
- Code ONLY Stage 2 elements
- Output valid JSON format"""
    
    try:
        # Call Claude API
        message = client.messages.create(
            model="claude-sonnet-4-20250514",  # Latest Sonnet 4
            max_tokens=4096,
            temperature=0,  # Deterministic for consistency
            system=system_prompt,
            messages=[
                {
                    "role": "user", # LLM uses "user" role for user messages
                    "content": user_message
                }
            ]
        )
        
        # Extract response text
        response_text = message.content[0].text
        
        # Parse JSON (Claude should return JSON)
        # Handle markdown code blocks if present
        if '```json' in response_text:
            # Extract JSON from ```json ... ``` blocks
            json_start = response_text.find('```json') + 7
            json_end = response_text.find('```', json_start)
            response_text = response_text[json_start:json_end].strip()
        elif '```' in response_text:
            # Extract from generic code blocks
            json_start = response_text.find('```') + 3
            json_end = response_text.find('```', json_start)
            response_text = response_text[json_start:json_end].strip()
        
        # Parse the JSON
        coded_data = json.loads(response_text)
        
        # Add API metadata
        coded_data['_api_metadata'] = {
            'call_id': message.id,
            'model': message.model,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'input_tokens': message.usage.input_tokens,
            'output_tokens': message.usage.output_tokens
        }
        
        return coded_data, None
        
    except json.JSONDecodeError as e:
        error_msg = f"JSON parsing error: {str(e)}\nResponse preview: {response_text[:300]}"
        return None, error_msg
        
    except Exception as e:
        error_msg = f"API error: {str(e)}"
        return None, error_msg

def main():
    print(f"{'='*60}")
    print("CLAUDE API CODING - BLIND PROTOCOL")
    print(f"{'='*60}\n")
    
    # 1. Check API key
    api_key = os.getenv('LLM_API_KEY')
    if not api_key:
        print("❌ ERROR: LLM_API_KEY not found in .env file")
        print("\nPlease create a .env file with:")
        print("LLM_API_KEY=your-key-here")
        return
    
    print("✓ API key loaded")
    
    # 2. Initialize Anthropic client
    client = Anthropic(api_key=api_key)
    print("✓ Anthropic client initialized")
    
    # 3. Load system prompt
    try:
        system_prompt = load_system_prompt()
        print(f"Yay!!!! System prompt loaded ({len(system_prompt)} characters)")
        print(system_prompt[:200] + "...\n")
    except FileNotFoundError as e:
        print(f"Ouch!!! Error: {e}")
        print("\nPlease ensure stage2_prompt.md is saved in the prompts/ folder")
        return
    
    # 4. Load prepared transcripts
    input_file = Path('data/processed/transcripts_prepared_masked_ok.json')
    if not input_file.exists():
        print(f"ERROR: Prepared transcripts not found: {input_file}")
        print("\nPlease run prepare_and_mask.py first")
        return
    
    with open(input_file, 'r', encoding='utf-8') as f:
        transcripts = json.load(f)
    
    print(f"✓ Loaded {len(transcripts)} transcripts\n")
    
    # 5. Create output directory
    output_dir = Path('data/coded/llm_outputs')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 6. Process each transcript
    print(f"{'='*60}")
    print("CODING TRANSCRIPTS")
    print(f"{'='*60}\n")
    
    results = []
    errors = []
    skipped = []
    
    total_input_tokens = 0
    total_output_tokens = 0
    
    for i, transcript in enumerate(transcripts, 1):
        participant_id = transcript['participant_id']
        
        print(f"[{i}/{len(transcripts)}] Processing {participant_id}...", end=' ')
        
        # Check if already coded
        output_file = output_dir / f"{participant_id}_coded.json"
        if output_file.exists():
            print("CAUTION: Already coded (skipping)")
            skipped.append(participant_id)
            continue
        
        # Code transcript
        coded_data, error = code_transcript_with_claude(client, system_prompt, transcript)
        
        if error:
            print(f"✗ ERROR")
            print(f"    {error}\n")
            errors.append({
                'transcript_id': participant_id,
                'error': error
            })
            continue
        
        # Save result
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(coded_data, f, indent=2, ensure_ascii=False)
        
        # Track tokens
        if '_api_metadata' in coded_data:
            total_input_tokens += coded_data['_api_metadata']['input_tokens']
            total_output_tokens += coded_data['_api_metadata']['output_tokens']
        
        results.append(participant_id)
        print("✓ Done")
        
        # Rate limiting: 1 second between requests
        if i < len(transcripts):
            time.sleep(1)
    
    # 7. Save summary
    summary = {
        'total_transcripts': len(transcripts),
        'successfully_coded': len(results),
        'already_coded': len(skipped),
        'errors': len(errors),
        'error_details': errors,
        'token_usage': {
            'total_input_tokens': total_input_tokens,
            'total_output_tokens': total_output_tokens,
            'estimated_cost_usd': (total_input_tokens / 1_000_000 * 3.0) + 
                                  (total_output_tokens / 1_000_000 * 15.0)
        },
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    summary_file = output_dir / '_coding_summary.json'
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    # 8. Print final summary
    print(f"\n{'='*60}")
    print("CODING COMPLETE")
    print(f"{'='*60}")
    print(f"Total transcripts: {len(transcripts)}")
    print(f"Successfully coded: {len(results)}")
    print(f"Already coded (skipped): {len(skipped)}")
    print(f"Errors: {len(errors)}")
    
    if errors:
        print(f"\n❌ Errors occurred:")
        for error in errors:
            print(f"  - {error['transcript_id']}: {error['error'][:100]}")
    
    print(f"\n{'='*60}")
    print("TOKEN USAGE & COST")
    print(f"{'='*60}")
    print(f"Input tokens: {total_input_tokens:,}")
    print(f"Output tokens: {total_output_tokens:,}")
    print(f"Estimated cost: ${summary['token_usage']['estimated_cost_usd']:.2f}")
    
    print(f"\n{'='*60}")
    print(f"✓ Results saved to: {output_dir}")
    print(f"✓ Summary saved to: {summary_file}")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()