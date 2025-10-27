#!/usr/bin/env python3
"""
Create an EPUB file from the decoded Amazon book data with proper formatting.
"""

import json
from pathlib import Path
import sys
from ebooklib import epub


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 create_epub_new.py <book_dir>")
        sys.exit(1)

    book_dir = Path(sys.argv[1])

    # Load the TTF character mapping
    mapping_file = Path("ttf_character_mapping.json")
    if not mapping_file.exists():
        print(f"Mapping file not found: {mapping_file}")
        print("Run match_ttf_to_glyphs.py first!")
        return

    with open(mapping_file, encoding='utf-8') as f:
        char_mapping = json.load(f)

    print(f"Loaded character mapping: {len(char_mapping)} glyphs")

    # Load metadata
    metadata_file = book_dir / 'batch_0' / 'metadata.json'
    with open(metadata_file) as f:
        metadata = json.load(f)

    # Load TOC
    toc_file = book_dir / 'batch_0' / 'toc.json'
    with open(toc_file) as f:
        toc_data = json.load(f)

    print(f"Book: {metadata['bookTitle']}")
    print(f"Author: {metadata['authors'][0]}")
    print(f"TOC entries: {len(toc_data)}")

    # Load all_glyphs
    all_glyphs_file = book_dir / 'hash_mapping' / 'all_glyphs.json'
    if not all_glyphs_file.exists():
        print(f"Book file not found: {all_glyphs_file}")
        return

    with open(all_glyphs_file) as f:
        all_glyphs = json.load(f)

    print(f"Loaded {len(all_glyphs)} glyphs from all_glyphs.json")

    # Build line ending info (where newlines go) - same as decode_book_with_newlines.py
    print("Building line ending positions...")
    batch_dirs = sorted([d for d in book_dir.iterdir() if d.is_dir() and d.name.startswith('batch_')],
                       key=lambda x: int(x.name.split('_')[1]))

    line_info = {}  # Index in all_glyphs -> formatting info
    current_index = 0

    # Get page dimensions from actual page data
    first_page_file = batch_dirs[0] / sorted(batch_dirs[0].glob('page_data_*.json'))[0].name
    with open(first_page_file) as f:
        first_page_data = json.load(f)
    page_width = first_page_data[0]['width']
    page_height = first_page_data[0]['height']

    print(f"Page dimensions: {page_width}x{page_height}")

    prev_y = None  # Track Y coordinate to detect line breaks

    for batch_dir in batch_dirs:
        page_files = sorted(batch_dir.glob('page_data_*.json'))
        for page_file in page_files:
            with open(page_file) as f:
                pages = json.load(f)

            for page in pages:
                for run in page.get('children', []):
                    if 'glyphs' not in run:
                        continue

                    num_glyphs = len(run['glyphs'])

                    # Extract formatting info with transform applied
                    rect = run.get('rect', {})
                    transform = run.get('transform', [1, 0, 0, 1, 0, 0])
                    tx = transform[4] if len(transform) >= 6 else 0
                    ty = transform[5] if len(transform) >= 6 else 0

                    left = rect.get('left', 0) + tx
                    right = rect.get('right', 0) + tx
                    top = rect.get('top', 0) + ty
                    font_style = run.get('fontStyle', 'normal')
                    font_weight = run.get('fontWeight', 400)
                    font_size = run.get('fontSize', 8.91)  # Default from downloader.py
                    has_link = 'link' in run

                    # Detect alignment type using relative thresholds
                    center = (left + right) / 2
                    page_center = page_width / 2
                    text_width = right - left
                    alignment = 'left'

                    # Use relative thresholds based on page width
                    center_tolerance = page_width * 0.05  # 5% of page width
                    edge_tolerance = page_width * 0.05    # 5% tolerance for edges
                    min_side_margin = page_width * 0.1    # 10% margin on each side for center
                    min_left_margin_right = page_width * 0.2  # 20% left margin for right-align
                    min_indent = page_width * 0.05        # 5% indent
                    max_indent = page_width * 0.15        # 15% max for paragraph indent
                    min_text_width = page_width * 0.3     # 30% minimum text width

                    # Check if centered: text center near page center AND margins on both sides
                    if abs(center - page_center) < center_tolerance and left > min_side_margin and (page_width - right) > min_side_margin:
                        alignment = 'center'
                    # Check if right-aligned: close to right edge with significant left margin
                    elif abs(right - page_width) < edge_tolerance and left > min_left_margin_right:
                        alignment = 'right'
                    # Check for indented paragraphs: moderate left margin with substantial text
                    elif min_indent < left < max_indent and text_width > min_text_width:
                        alignment = 'indent'

                    # Determine if this is a new line (Y coordinate changed significantly)
                    is_new_line = prev_y is None or abs(top - prev_y) > 5

                    # Store info for each glyph position in this run
                    for i in range(num_glyphs):
                        line_info[current_index + i] = {
                            'font_style': font_style,
                            'font_weight': font_weight,
                            'font_size': font_size,
                            'has_link': has_link,
                            'left': left,
                            'alignment': alignment
                        }

                    # Only mark line break if this run is on a NEW line
                    if is_new_line and current_index > 0:
                        # Mark line break at the END of the PREVIOUS run
                        line_info[current_index - 1]['line_break'] = True

                    current_index += num_glyphs
                    prev_y = top

    print(f"Processed {current_index} glyphs with line break info")

    # Create EPUB
    print("Creating EPUB...")
    book = epub.EpubBook()

    # Set metadata
    book.set_identifier(metadata.get('asin', 'unknown'))
    book.set_title(metadata['bookTitle'])
    book.set_language(metadata.get('lang', 'en'))

    for author in metadata.get('authors', ['Unknown']):
        book.add_author(author)


    # Add CSS for styling - match Kindle rendering parameters
    # Based on downloader.py: fontFamily='Bookerly', fontSize='8.91', lineHeight='1.4'
    style = '''
        body {
            font-family: Bookerly, Georgia, serif;
            font-size: 8pt;
            line-height: 1.0;
            margin: 0 auto;
            padding: 0;
            max-width: 1000px;
            background-color: #ffffff;
            color: #000000;
        }
        p {
            margin: 0;
            padding: 0;
            line-height: 1.0;
        }
        p.center {
            text-align: center;
        }
        p.right {
            text-align: right;
        }
        p.indent {
            text-indent: 2em;
        }
        p.break {
            margin-top: 0.8em;
        }
        .italic { font-style: italic; }
        .bold { font-weight: bold; }
        .link {
            color: #0066cc;
            text-decoration: underline;
        }
        h1 {
            font-size: 1.8em;
            margin: 1em 0 0.5em 0;
            font-weight: bold;
        }
        h2 {
            font-size: 1.4em;
            margin: 0.8em 0 0.4em 0;
            font-weight: bold;
        }
    '''

    default_css = epub.EpubItem(
        uid="style_default",
        file_name="style/default.css",
        media_type="text/css",
        content=style
    )
    book.add_item(default_css)

    # Map position IDs to glyph indices
    print("Mapping TOC positions to glyph indices...")
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
                        position_to_glyph_idx[start_pos_id] = current_glyph_idx

                    current_glyph_idx += len(run['glyphs'])

    # Flatten nested TOC structure to get all chapters, avoiding duplicates
    def flatten_toc_entries(toc_data):
        """Flatten nested TOC structure, skipping section headers that duplicate sub-chapters"""
        flattened = []
        for entry in toc_data:
            # Check if this entry has sub-entries
            if 'entries' in entry and entry['entries']:
                # Check if the main entry has the same position as the first sub-entry
                first_sub_pos = entry['entries'][0]['tocPositionId']
                if entry['tocPositionId'] == first_sub_pos:
                    # Skip the section header, only add sub-entries
                    for sub_entry in entry['entries']:
                        flattened.append(sub_entry)
                else:
                    # Add both the main entry and sub-entries
                    flattened.append(entry)
                    for sub_entry in entry['entries']:
                        flattened.append(sub_entry)
            else:
                # No sub-entries, add the main entry
                flattened.append(entry)
        return flattened

    flat_toc_data = flatten_toc_entries(toc_data)
    print(f"Flattened TOC: {len(toc_data)} main entries -> {len(flat_toc_data)} total entries")
    
    # Map TOC entries to glyph indices with fuzzy matching
    toc_chapters = []
    for i, toc_entry in enumerate(flat_toc_data):
        target_pos = toc_entry['tocPositionId']
        
        # First try exact match
        if target_pos in position_to_glyph_idx:
            toc_chapters.append({
                'label': toc_entry['label'],
                'glyph_idx': position_to_glyph_idx[target_pos],
                'chapter_num': i
            })
        else:
            # Try fuzzy matching - find closest position within small range
            closest_pos = None
            min_distance = float('inf')
            
            for pos_id in position_to_glyph_idx:
                distance = abs(pos_id - target_pos)
                if distance < min_distance and distance <= 10:  # Within 10 positions
                    min_distance = distance
                    closest_pos = pos_id
            
            if closest_pos is not None:
                toc_chapters.append({
                    'label': toc_entry['label'],
                    'glyph_idx': position_to_glyph_idx[closest_pos],
                    'chapter_num': i
                })
                print(f"  Using fuzzy match: {toc_entry['label']} (target {target_pos} -> actual {closest_pos}, distance {min_distance})")
            else:
                print(f"  No match found for: {toc_entry['label']} (position {target_pos})")

    print(f"Found {len(toc_chapters)} TOC entries with positions")

    # Build chapters based on TOC structure
    print("Building chapters with formatting...")
    import html
    chapters = []
    chapter_contents = {}  # chapter_num -> content list
    current_chapter_num = -1  # Start before first chapter
    current_span_classes = []
    consecutive_line_breaks = 0

    for idx, glyph_id in enumerate(all_glyphs):
        # Check if we're at a new chapter start
        for toc_ch in toc_chapters:
            if toc_ch['glyph_idx'] == idx:
                current_chapter_num = toc_ch['chapter_num']
                if current_chapter_num not in chapter_contents:
                    chapter_contents[current_chapter_num] = ['<p>']
                break

        # Skip content before first chapter
        if current_chapter_num == -1:
            continue

        # Decode this glyph
        glyph_key = str(glyph_id)
        if glyph_key in char_mapping:
            char = char_mapping[glyph_key]["character"]
        else:
            char = f"[{glyph_id}]"

        # Get formatting for this position
        info = line_info.get(idx, {})
        font_style = info.get('font_style', 'normal')
        font_weight = info.get('font_weight', 400)
        font_size = info.get('font_size', 8.91)
        has_link = info.get('has_link', False)
        alignment = info.get('alignment', 'left')

        # Determine classes and inline styles needed
        classes = []
        if font_style == 'italic':
            classes.append('italic')
        if font_weight >= 700:
            classes.append('bold')
        if has_link:
            classes.append('link')

        # Add font size as inline style if it differs significantly from base (8.91pt)
        font_size_style = ''
        if abs(font_size - 8.91) > 1.0:  # More than 1pt difference
            # Convert to relative em size (base is 8pt in CSS)
            em_size = font_size / 8.0
            font_size_style = f'font-size: {em_size:.2f}em'

        # If classes changed, close previous span and open new one
        if classes != current_span_classes:
            if current_span_classes:
                chapter_contents[current_chapter_num].append('</span>')
            if classes:
                class_attr = f' class="{" ".join(classes)}"'
                style_attr = f' style="{font_size_style}"' if font_size_style else ''
                chapter_contents[current_chapter_num].append(f'<span{class_attr}{style_attr}>')
            elif font_size_style:
                # Font size change without class changes
                chapter_contents[current_chapter_num].append(f'<span style="{font_size_style}">')
            current_span_classes = classes

        # Add the character
        chapter_contents[current_chapter_num].append(html.escape(char))

        # Check if this is a line break position
        if info.get('line_break', False):
            # Detect bullet point context to keep bullets with their text
            is_current_bullet = char in ['•', '◦', '●']

            prev_is_bullet = False
            for look_back in range(1, min(5, idx + 1)):
                prev_char = char_mapping.get(str(all_glyphs[idx - look_back]), {}).get("character", "")
                if prev_char in ['•', '◦', '●']:
                    prev_is_bullet = True
                    break
                elif prev_char != ' ':
                    break

            if current_span_classes:
                chapter_contents[current_chapter_num].append('</span>')
                current_span_classes = []

            # Suppress line breaks after bullets to keep them with their text
            if is_current_bullet or prev_is_bullet:
                consecutive_line_breaks = 0
            else:
                consecutive_line_breaks += 1

                next_alignment = 'left'
                if idx + 1 < len(all_glyphs):
                    next_info = line_info.get(idx + 1, {})
                    next_alignment = next_info.get('alignment', 'left')

                classes = []
                if consecutive_line_breaks >= 2:
                    classes.append('break')
                    consecutive_line_breaks = 0
                if next_alignment in ['center', 'right', 'indent']:
                    classes.append(next_alignment)

                class_str = f' class="{" ".join(classes)}"' if classes else ''
                chapter_contents[current_chapter_num].append(f'</p>\n<p{class_str}>')
        else:
            consecutive_line_breaks = 0

    # Create EPUB chapters
    print("Creating EPUB chapters...")
    for toc_ch in toc_chapters:
        ch_num = toc_ch['chapter_num']
        if ch_num in chapter_contents:
            chapter_contents[ch_num].append('</p>')

            chapter = epub.EpubHtml(
                title=toc_ch['label'],
                file_name=f'chap_{ch_num:03d}.xhtml',
                lang=metadata.get('lang', 'en')
            )
            chapter.content = ''.join(chapter_contents[ch_num])
            chapter.add_item(default_css)
            book.add_item(chapter)
            chapters.append(chapter)

    # Define Table of Contents
    book.toc = tuple(chapters)

    # Add navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define spine
    book.spine = ['nav'] + chapters

    # Save EPUB
    output_file = Path("decoded_book.epub")
    epub.write_epub(str(output_file), book)

    print(f"\nEPUB created successfully: {output_file}")
    print(f"Total chapters: {len(chapters)}")

if __name__ == "__main__":
    main()
