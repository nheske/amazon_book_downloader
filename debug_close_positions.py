import json
from pathlib import Path

book_dir = Path('downloads/B07TM8LMRW')

# Load TOC
with open(book_dir / 'batch_0/toc.json') as f:
    toc_data = json.load(f)

toc_positions = {entry['tocPositionId'] for entry in toc_data}
print(f"TOC positions needed: {sorted(toc_positions)}")

# Build position mapping from all batches
batch_dirs = sorted([d for d in book_dir.iterdir() if d.is_dir() and d.name.startswith('batch_')])

all_positions = set()
position_to_glyph_idx = {}
current_glyph_idx = 0

for batch_dir in batch_dirs:
    page_files = sorted(batch_dir.glob('page_data_*.json'))
    
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
                    all_positions.add(start_pos_id)
                    position_to_glyph_idx[start_pos_id] = current_glyph_idx

                current_glyph_idx += len(run['glyphs'])

print(f"\nAll available positions: {len(all_positions)}")
print(f"Position range: {min(all_positions)} to {max(all_positions)}")

# Find positions close to TOC positions
print(f"\nLooking for positions near TOC entries:")
for entry in toc_data:
    target = entry['tocPositionId']
    label = entry['label']
    
    # Find closest positions
    distances = [(abs(pos - target), pos) for pos in all_positions]
    distances.sort()
    closest = distances[:3]
    
    print(f"{label} (target {target}): closest positions {[pos for _, pos in closest]}")
    
    # Check if exact match exists
    if target in all_positions:
        print(f"  ✓ EXACT MATCH found at position {target}")
    else:
        # Use closest position within reasonable range
        closest_dist, closest_pos = closest[0]
        if closest_dist <= 100:  # Within 100 positions
            print(f"  ~ Using closest position {closest_pos} (distance: {closest_dist})")
        else:
            print(f"  ✗ No close match (closest: {closest_pos}, distance: {closest_dist})")