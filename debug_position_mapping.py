import json
from pathlib import Path

book_dir = Path('downloads/B07TM8LMRW')

# Load TOC
with open(book_dir / 'batch_0/toc.json') as f:
    toc_data = json.load(f)

print(f"TOC entries: {len(toc_data)}")

# Build position mapping from all batches
batch_dirs = sorted([d for d in book_dir.iterdir() if d.is_dir() and d.name.startswith('batch_')])
print(f"Found {len(batch_dirs)} batches")

position_to_glyph_idx = {}
current_glyph_idx = 0

for batch_dir in batch_dirs:
    page_files = sorted(batch_dir.glob('page_data_*.json'))
    print(f"Batch {batch_dir.name}: {len(page_files)} page files")
    
    for page_file in page_files:
        with open(page_file) as f:
            pages = json.load(f)

        for page in pages:
            for run in page.get('children', []):
                if 'glyphs' not in run:
                    continue

                # Check if this run has position info
                start_pos_id = run.get('startPositionId')
                if start_pos_id is not None:
                    position_to_glyph_idx[start_pos_id] = current_glyph_idx
                    if start_pos_id in [entry['tocPositionId'] for entry in toc_data]:
                        print(f"Found TOC position {start_pos_id} at glyph index {current_glyph_idx}")

                current_glyph_idx += len(run['glyphs'])

print(f"\nTotal glyphs processed: {current_glyph_idx}")
print(f"Total position mappings found: {len(position_to_glyph_idx)}")

# Check which TOC entries have position mappings
toc_chapters = []
for i, toc_entry in enumerate(toc_data):
    pos_id = toc_entry['tocPositionId']
    if pos_id in position_to_glyph_idx:
        toc_chapters.append({
            'label': toc_entry['label'],
            'glyph_idx': position_to_glyph_idx[pos_id],
            'chapter_num': i
        })
        print(f"✓ TOC {i}: {toc_entry['label']} -> position {pos_id} -> glyph {position_to_glyph_idx[pos_id]}")
    else:
        print(f"✗ TOC {i}: {toc_entry['label']} -> position {pos_id} -> NOT FOUND")

print(f"\nMapped TOC entries: {len(toc_chapters)}")