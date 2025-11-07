#!/usr/bin/env python3
"""
Better chapter detection for Modern Poker Theory - look for actual chapter starts
"""

import sys
from pathlib import Path
import re
from PyPDF2 import PdfReader, PdfWriter

def find_real_chapters(pdf_path):
    """
    Find the real chapter boundaries by looking for proper chapter headings
    """
    reader = PdfReader(pdf_path)
    chapters = []
    
    print("[*] Scanning entire PDF for chapter patterns...")
    
    # Look for major section headers that are likely real chapters
    chapter_patterns = [
        (r'^0?(\d{1,2})$', 'numbered'),  # Just the number (01, 02, 1, 2, etc.)
        (r'^Chapter\s+(\d+)', 'chapter_word'),
        (r'^PART\s+(\d+)', 'part')
    ]
    
    # Track what we find
    found_chapters = {}
    
    for page_num, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
            if not text.strip():
                continue
                
            lines = text.split('\n')
            
            # Look at the first several lines of each page for chapter markers
            for line_idx, line in enumerate(lines[:15]):  # Check first 15 lines
                line = line.strip()
                
                for pattern, pattern_type in chapter_patterns:
                    match = re.match(pattern, line)
                    if match:
                        chapter_num = int(match.group(1))
                        
                        # Only reasonable chapter numbers
                        if chapter_num < 1 or chapter_num > 20:
                            continue
                            
                        # Look for chapter title in next few lines
                        title_lines = []
                        for next_idx in range(line_idx + 1, min(line_idx + 8, len(lines))):
                            next_line = lines[next_idx].strip()
                            
                            # Skip empty lines
                            if not next_line:
                                continue
                                
                            # Stop at page numbers or other metadata
                            if re.match(r'^\d+$', next_line) and len(next_line) <= 3:
                                break
                            if any(stop in next_line.lower() for stop in ['page ', 'figure', 'table', '©', 'copyright']):
                                break
                                
                            # Collect potential title text
                            if len(next_line) > 3:
                                title_lines.append(next_line)
                                
                            # Stop after collecting a reasonable title
                            if len(' '.join(title_lines)) > 15:
                                break
                        
                        if title_lines:
                            full_title = ' '.join(title_lines)
                            
                            # Validate the title
                            if (len(full_title) >= 5 and len(full_title) <= 100 and
                                not full_title.lower().startswith(('and ', 'or ', 'but ', 'of ', 'in '))):
                                
                                # Check if this is better than what we already found
                                key = chapter_num
                                if key not in found_chapters or page_num > 20:  # Prefer chapters after TOC
                                    found_chapters[key] = {
                                        'number': chapter_num,
                                        'title': full_title,
                                        'page': page_num,
                                        'pattern_type': pattern_type
                                    }
                                    print(f"  Chapter {chapter_num:02d} on page {page_num + 1}: {full_title[:60]}")
                        break
                        
        except Exception as e:
            continue
    
    # Convert to sorted list
    chapters = sorted(found_chapters.values(), key=lambda x: x['number'])
    print(f"\n[*] Found {len(chapters)} valid chapters")
    
    return chapters

def create_clean_chapter_pdfs(pdf_path, output_dir, chapters):
    """
    Create chapter PDFs with proper page ranges
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
            
            # Find end page - start of next chapter or end of book
            if i < len(chapters) - 1:
                end_page = chapters[i + 1]['page'] - 1
            else:
                end_page = len(reader.pages) - 1
            
            # Add pages
            page_count = 0
            for page_num in range(start_page, end_page + 1):
                if page_num < len(reader.pages):
                    writer.add_page(reader.pages[page_num])
                    page_count += 1
            
            if page_count > 0:
                # Clean title for filename
                clean_title = re.sub(r'[<>:"/\\|?*]', '_', chapter['title'])
                clean_title = clean_title.strip()[:50]  # Limit length
                
                filename = f"chapter_{chapter['number']:02d}_{clean_title}.pdf"
                output_path = output_dir / filename
                
                with open(output_path, 'wb') as output_file:
                    writer.write(output_file)
                
                file_size = output_path.stat().st_size / 1024  # KB
                print(f"[✓] Chapter {chapter['number']:02d}: {filename} ({page_count} pages, {file_size:.0f}KB)")
                successful += 1
            else:
                print(f"[✗] Chapter {chapter['number']:02d}: No pages found")
                
        except Exception as e:
            print(f"[✗] Failed to create chapter {chapter['number']:02d}: {e}")
    
    return successful > 0

def main():
    if len(sys.argv) < 2:
        print("Usage: python clean_chapter_split.py <pdf_file> [output_dir]")
        sys.exit(1)
    
    pdf_path = Path(sys.argv[1])
    output_dir = sys.argv[2] if len(sys.argv) > 2 else f"output/{pdf_path.stem}_clean_chapters"
    
    if not pdf_path.exists():
        print(f"[✗] PDF not found: {pdf_path}")
        sys.exit(1)
    
    print(f"[*] Processing: {pdf_path.name}")
    print(f"[*] Output directory: {output_dir}")
    
    chapters = find_real_chapters(pdf_path)
    
    if not chapters:
        print("[✗] No chapters found")
        sys.exit(1)
    
    print(f"\n[*] Creating {len(chapters)} chapter PDFs...")
    success = create_clean_chapter_pdfs(pdf_path, output_dir, chapters)
    
    if success:
        print(f"\n[✓] Successfully created chapter PDFs in: {output_dir}")
    else:
        print(f"\n[✗] Failed to create chapter PDFs")

if __name__ == "__main__":
    main()