#!/usr/bin/env python3
"""
Smart chapter detection for PDFs using multiple analysis methods
"""

import sys
import re
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter
from collections import defaultdict, Counter

def analyze_font_changes(reader):
    """
    Analyze font size changes that might indicate chapter starts
    """
    print("[*] Analyzing font size patterns...")
    font_changes = []
    
    for page_num in range(min(100, len(reader.pages))):  # Sample first 100 pages
        try:
            page = reader.pages[page_num]
            if '/Font' in page.get('/Resources', {}):
                # This is a simplified approach - real font analysis is complex
                # Look for pages with potential chapter markers
                text = page.extract_text()
                lines = text.split('\n')[:10]  # First 10 lines
                
                for i, line in enumerate(lines):
                    line = line.strip()
                    if len(line) < 50 and re.search(r'chapter\s+\d+', line, re.I):
                        font_changes.append((page_num, line))
                        
        except Exception:
            continue
    
    return font_changes

def analyze_page_breaks(reader):
    """
    Look for pages that start with chapter-like content
    """
    print("[*] Analyzing page break patterns...")
    chapter_candidates = []
    
    # Common chapter start patterns
    chapter_patterns = [
        r'^chapter\s+(\d+)',
        r'^(\d+)\s*[-–]\s*',  # "1 - Title" or "1– Title"
        r'^(\d+)\.\s+',       # "1. Title"
        r'^\d+\s+[A-Z][^a-z]*$',  # All caps titles after numbers
    ]
    
    for page_num in range(len(reader.pages)):
        try:
            page = reader.pages[page_num]
            text = page.extract_text()
            
            # Get first few non-empty lines
            lines = [line.strip() for line in text.split('\n') if line.strip()][:5]
            
            for pattern in chapter_patterns:
                for line in lines:
                    match = re.search(pattern, line, re.I)
                    if match:
                        chapter_num = match.group(1) if match.groups() else None
                        if chapter_num and chapter_num.isdigit():
                            chapter_candidates.append({
                                'page': page_num,
                                'number': int(chapter_num),
                                'title': line,
                                'confidence': 0.8 if 'chapter' in line.lower() else 0.6
                            })
                            break
                        
        except Exception:
            continue
    
    return chapter_candidates

def analyze_whitespace_patterns(reader):
    """
    Look for pages with unusual whitespace that might indicate chapter starts
    """
    print("[*] Analyzing whitespace patterns...")
    whitespace_candidates = []
    
    for page_num in range(len(reader.pages)):
        try:
            page = reader.pages[page_num]
            text = page.extract_text()
            
            # Count lines and estimate whitespace
            lines = text.split('\n')
            non_empty_lines = [line for line in lines if line.strip()]
            
            # Look for pages that start with significant whitespace
            if len(lines) > 20:  # Reasonable page length
                first_text_line = next((i for i, line in enumerate(lines) if line.strip()), 0)
                
                # If first text appears after significant whitespace
                if first_text_line > 5 and len(non_empty_lines) < len(lines) * 0.7:
                    # Check if the first text looks like a chapter
                    first_line = lines[first_text_line].strip()
                    if (len(first_line) < 80 and 
                        any(word in first_line.lower() for word in ['chapter', 'part', 'section'])):
                        
                        whitespace_candidates.append({
                            'page': page_num,
                            'title': first_line,
                            'whitespace_ratio': first_text_line / len(lines),
                            'confidence': 0.4
                        })
                        
        except Exception:
            continue
    
    return whitespace_candidates

def merge_and_validate_chapters(font_changes, break_candidates, whitespace_candidates, reader):
    """
    Merge different detection methods and validate results
    """
    print("[*] Merging and validating chapter candidates...")
    
    # Combine all candidates
    all_candidates = []
    
    # Add break candidates (highest confidence)
    for candidate in break_candidates:
        all_candidates.append({
            'page': candidate['page'],
            'number': candidate.get('number'),
            'title': candidate['title'],
            'confidence': candidate['confidence'],
            'method': 'pattern'
        })
    
    # Add font change candidates
    for page, title in font_changes:
        # Extract chapter number if possible
        match = re.search(r'(\d+)', title)
        chapter_num = int(match.group(1)) if match else None
        
        all_candidates.append({
            'page': page,
            'number': chapter_num,
            'title': title,
            'confidence': 0.7,
            'method': 'font'
        })
    
    # Add whitespace candidates (lower confidence)
    for candidate in whitespace_candidates:
        all_candidates.append({
            'page': candidate['page'],
            'number': None,
            'title': candidate['title'],
            'confidence': candidate['confidence'],
            'method': 'whitespace'
        })
    
    # Remove duplicates (same page)
    page_candidates = {}
    for candidate in all_candidates:
        page = candidate['page']
        if page not in page_candidates or candidate['confidence'] > page_candidates[page]['confidence']:
            page_candidates[page] = candidate
    
    # Convert back to list and sort by page
    candidates = list(page_candidates.values())
    candidates.sort(key=lambda x: x['page'])
    
    # Validate candidates
    validated = []
    for candidate in candidates:
        # Skip if chapter number is unreasonable
        if candidate.get('number') and candidate['number'] > 50:
            continue
            
        # Skip if title is too long or looks like body text
        title = candidate['title']
        if len(title) > 200 or title.count('.') > 3:
            continue
            
        # Check page content quality
        try:
            page_text = reader.pages[candidate['page']].extract_text()
            word_count = len(page_text.split())
            
            # Skip nearly empty pages
            if word_count < 50:
                continue
                
            validated.append(candidate)
            
        except Exception:
            continue
    
    return validated

def create_smart_chapter_pdfs(pdf_path, output_dir, chapters):
    """
    Create chapter PDFs from detected chapters
    """
    reader = PdfReader(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    successful = 0
    
    for i, chapter in enumerate(chapters):
        try:
            writer = PdfWriter()
            
            # Determine page range
            start_page = chapter['page']
            
            # End page is start of next chapter minus 1, or end of book
            if i < len(chapters) - 1:
                end_page = chapters[i + 1]['page'] - 1
            else:
                end_page = len(reader.pages) - 1
            
            # Ensure reasonable chapter length
            page_count = end_page - start_page + 1
            if page_count < 2:  # Skip very short chapters
                print(f"[⚠] Skipping short chapter: {chapter['title'][:50]}... ({page_count} pages)")
                continue
            
            # Add pages
            actual_pages = 0
            for page_num in range(start_page, end_page + 1):
                if page_num < len(reader.pages):
                    writer.add_page(reader.pages[page_num])
                    actual_pages += 1
            
            if actual_pages > 0:
                # Create clean filename
                title = chapter['title'].replace('/', '_').replace(':', '_').replace('\\', '_')
                if len(title) > 80:
                    title = title[:80] + "..."
                
                chapter_num = chapter.get('number', i + 1)
                filename = f"chapter_{chapter_num:02d}_{title}.pdf"
                output_path = output_dir / filename
                
                with open(output_path, 'wb') as output_file:
                    writer.write(output_file)
                
                file_size = output_path.stat().st_size / 1024  # KB
                method = chapter.get('method', 'unknown')
                conf = chapter.get('confidence', 0)
                
                print(f"[✓] Chapter {chapter_num:02d}: {filename[:60]}... ({actual_pages} pages, {file_size:.0f}KB) [{method}, {conf:.1f}]")
                successful += 1
            else:
                print(f"[✗] No pages for chapter: {chapter['title'][:50]}...")
                
        except Exception as e:
            print(f"[✗] Failed to create chapter: {e}")
    
    return successful

def main():
    if len(sys.argv) < 2:
        print("Usage: python smart_chapter_split.py <pdf_file> [output_dir]")
        sys.exit(1)
    
    pdf_path = Path(sys.argv[1])
    output_dir = sys.argv[2] if len(sys.argv) > 2 else f"output/{pdf_path.stem}_smart_chapters"
    
    if not pdf_path.exists():
        print(f"[✗] PDF not found: {pdf_path}")
        sys.exit(1)
    
    print(f"[*] Smart chapter detection for: {pdf_path.name}")
    print(f"[*] Output directory: {output_dir}")
    
    # Load PDF
    reader = PdfReader(pdf_path)
    print(f"[*] PDF has {len(reader.pages)} pages")
    
    # Run different detection methods
    font_changes = analyze_font_changes(reader)
    break_candidates = analyze_page_breaks(reader)
    whitespace_candidates = analyze_whitespace_patterns(reader)
    
    print(f"[*] Found {len(font_changes)} font-based candidates")
    print(f"[*] Found {len(break_candidates)} pattern-based candidates")
    print(f"[*] Found {len(whitespace_candidates)} whitespace-based candidates")
    
    # Merge and validate
    chapters = merge_and_validate_chapters(font_changes, break_candidates, whitespace_candidates, reader)
    
    if not chapters:
        print("[✗] No valid chapters detected")
        sys.exit(1)
    
    print(f"\n[*] Validated {len(chapters)} chapters:")
    for chapter in chapters:
        method = chapter.get('method', '?')
        conf = chapter.get('confidence', 0)
        print(f"  Page {chapter['page'] + 1:3d}: {chapter['title'][:60]}... [{method}, {conf:.1f}]")
    
    print(f"\n[*] Creating chapter PDFs...")
    successful = create_smart_chapter_pdfs(pdf_path, output_dir, chapters)
    
    if successful:
        print(f"\n[✓] Successfully created {successful} chapter PDFs")
        print(f"[*] Output directory: {output_dir}")
    else:
        print(f"\n[✗] Failed to create chapter PDFs")

if __name__ == "__main__":
    main()