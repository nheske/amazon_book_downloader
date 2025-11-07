#!/usr/bin/env python3
"""
Improved PDF Chapter Splitter - Better chapter detection for Modern Poker Theory style books
"""

import sys
import os
from pathlib import Path
import re
from PyPDF2 import PdfReader, PdfWriter

def find_chapter_pages_modern_poker(pdf_path):
    """
    Find chapter pages specifically for Modern Poker Theory style books
    
    Args:
        pdf_path (Path): Path to PDF file
    
    Returns:
        list: List of chapter information
    """
    reader = PdfReader(pdf_path)
    chapters = []
    
    print("[*] Scanning for chapter headings (numbered format)...")
    
    # Look for pages that start with a large chapter number (01, 02, etc.)
    for page_num, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
            lines = text.split('\n')
            
            # Skip very short pages (likely blanks)
            if len(text.strip()) < 50:
                continue
            
            # Look for chapter pattern at beginning of page
            for i, line in enumerate(lines[:10]):  # Check first 10 lines
                line = line.strip()
                
                # Pattern: Two digits on their own line, followed by chapter title
                if re.match(r'^\d{2}$', line) and i < len(lines) - 1:
                    chapter_num = int(line)
                    
                    # Only accept reasonable chapter numbers (1-30 for most books)
                    if chapter_num > 30:
                        continue
                    
                    # Get next few lines as potential title
                    title_parts = []
                    for j in range(i + 1, min(i + 5, len(lines))):
                        next_line = lines[j].strip()
                        if next_line and len(next_line) > 3:
                            # Stop at common non-title patterns
                            if any(stop_word in next_line.lower() for stop_word in ['page ', 'figure ', 'table ', 'diagram ', 'copyright', '©']):
                                break
                            title_parts.append(next_line)
                    
                    if title_parts:
                        full_title = ' '.join(title_parts[:2])  # Use first 2 lines
                        
                        # Validate the title - should not start with lowercase words or conjunctions
                        if full_title.lower().startswith(('and ', 'or ', 'but ', 'the ', 'of ', 'in ', 'at ', 'on ')):
                            continue
                        
                        # Should be a reasonable length for a chapter title
                        if len(full_title.strip()) < 5 or len(full_title) > 100:
                            continue
                        
                        chapters.append({
                            'number': chapter_num,
                            'title': full_title,
                            'page': page_num,
                            'chapter_type': 'numbered'
                        })
                        
                        print(f"  Found Chapter {chapter_num:02d} on page {page_num + 1}: {full_title[:50]}")
                        break
                        
        except Exception as e:
            continue
    
    # Remove duplicates - prefer actual chapter headings over TOC entries
    # TOC entries are usually in the first 20 pages, actual chapters later
    unique_chapters = {}
    for ch in chapters:
        if ch['number'] not in unique_chapters:
            unique_chapters[ch['number']] = ch
        else:
            existing = unique_chapters[ch['number']]
            # Prefer the one that's NOT in the first 20 pages (likely TOC)
            if ch['page'] >= 20 and existing['page'] < 20:
                unique_chapters[ch['number']] = ch
            elif existing['page'] >= 20 and ch['page'] < 20:
                # Keep existing (it's the real chapter)
                pass
            else:
                # Both are in same section, keep the one with better title
                if len(ch['title']) > len(existing['title']):
                    unique_chapters[ch['number']] = ch
    
    # Sort by chapter number for logical order
    final_chapters = sorted(unique_chapters.values(), key=lambda x: x['number'])
    
    print(f"[*] Found {len(final_chapters)} unique chapters")
    return final_chapters

def create_chapter_pdfs_modern_poker(pdf_path, output_dir, chapters):
    """
    Create chapter PDFs based on detected chapters
    
    Args:
        pdf_path (Path): Input PDF path
        output_dir (Path): Output directory
        chapters (list): Chapter information
    
    Returns:
        bool: Success status
    """
    reader = PdfReader(pdf_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    successful = 0
    
    for i, chapter in enumerate(chapters):
        try:
            writer = PdfWriter()
            
            # Determine page range
            start_page = chapter['page']
            
            # Find end page (start of next chapter or end of book)
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
                clean_title = clean_title.strip()[:40]  # Limit length
                
                filename = f"chapter_{chapter['number']:02d}_{clean_title}.pdf"
                output_path = output_dir / filename
                
                with open(output_path, 'wb') as output_file:
                    writer.write(output_file)
                
                file_size = output_path.stat().st_size / 1024  # KB
                print(f"[✓] Chapter {chapter['number']:02d}: {filename} ({page_count} pages, {file_size:.1f}KB)")
                successful += 1
            else:
                print(f"[✗] Chapter {chapter['number']:02d}: No pages to extract")
                
        except Exception as e:
            print(f"[✗] Failed to create chapter {chapter['number']:02d}: {e}")
    
    return successful > 0

def split_modern_poker_theory(pdf_path, output_dir=None):
    """
    Main function to split Modern Poker Theory style PDFs
    
    Args:
        pdf_path (str): Path to PDF file
        output_dir (str, optional): Output directory
    
    Returns:
        bool: Success status
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        print(f"[✗] PDF file not found: {pdf_path}")
        return False
    
    if output_dir is None:
        # Default to output folder structure
        output_dir = pdf_path.parent / "output" / f"{pdf_path.stem}_chapters"
    else:
        output_dir = Path(output_dir)
    
    print(f"[*] Processing: {pdf_path.name}")
    print(f"[*] Output directory: {output_dir}")
    
    # Find chapters
    chapters = find_chapter_pages_modern_poker(pdf_path)
    
    if not chapters:
        print("[✗] No chapters found")
        return False
    
    print(f"\n[*] Chapter summary:")
    for ch in chapters:
        print(f"  {ch['number']:02d}: {ch['title'][:50]} (page {ch['page'] + 1})")
    
    # Confirm before proceeding
    print(f"\n[?] Create {len(chapters)} chapter PDFs? (y/n): ", end="")
    response = input().lower().strip()
    
    if response != 'y' and response != 'yes':
        print("[*] Cancelled by user")
        return False
    
    # Create chapter PDFs
    success = create_chapter_pdfs_modern_poker(pdf_path, output_dir, chapters)
    
    if success:
        print(f"\n[✓] Successfully split PDF into chapters")
        print(f"[*] Output directory: {output_dir}")
    
    return success

def main():
    if len(sys.argv) < 2:
        print("Usage: python split_modern_poker.py <pdf_file> [output_directory]")
        print("Example: python split_modern_poker.py modern_poker_theory.pdf chapters/")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = split_modern_poker_theory(pdf_file, output_dir)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()