#!/usr/bin/env python3
"""
PDF Chapter Splitter

This script splits a PDF into individual chapter PDFs based on bookmarks/outline structure
or by detecting chapter headings in the text.
"""

import sys
import os
from pathlib import Path
import re
try:
    import PyPDF2
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:
    print("[✗] PyPDF2 not installed. Installing...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "PyPDF2"], check=True)
    import PyPDF2
    from PyPDF2 import PdfReader, PdfWriter

def analyze_pdf_structure(pdf_path):
    """
    Analyze PDF structure to understand how to split it
    
    Args:
        pdf_path (Path): Path to PDF file
    
    Returns:
        dict: Analysis results
    """
    reader = PdfReader(pdf_path)
    
    analysis = {
        'total_pages': len(reader.pages),
        'has_outline': False,
        'outline_items': [],
        'title': reader.metadata.get('/Title', 'Unknown') if reader.metadata else 'Unknown'
    }
    
    # Check for outline/bookmarks
    if reader.outline:
        analysis['has_outline'] = True
        analysis['outline_items'] = extract_outline_structure(reader.outline)
    
    return analysis

def extract_outline_structure(outline, level=0):
    """
    Extract hierarchical outline structure from PDF
    
    Args:
        outline: PDF outline object
        level (int): Current nesting level
    
    Returns:
        list: Structured outline items
    """
    items = []
    
    for item in outline:
        if isinstance(item, list):
            # Nested outline
            items.extend(extract_outline_structure(item, level + 1))
        else:
            # Individual outline item
            try:
                page_num = item.page.idnum if hasattr(item.page, 'idnum') else None
                if page_num is None and hasattr(item, 'page'):
                    # Try to get page number differently
                    page_ref = item.page
                    if hasattr(page_ref, 'get_object'):
                        page_num = page_ref.get_object()
                
                items.append({
                    'title': item.title,
                    'level': level,
                    'page': page_num,
                    'raw_item': item
                })
            except Exception as e:
                print(f"[⚠] Warning: Could not process outline item '{item.title}': {e}")
                items.append({
                    'title': item.title,
                    'level': level,
                    'page': None,
                    'raw_item': item
                })
    
    return items

def get_page_number_from_destination(reader, destination):
    """
    Try to get page number from destination object
    
    Args:
        reader: PdfReader object
        destination: Destination object
    
    Returns:
        int or None: Page number (0-based)
    """
    try:
        if hasattr(destination, 'page'):
            page_ref = destination.page
            if hasattr(page_ref, 'get_object'):
                page_obj = page_ref.get_object()
                # Find this page in the reader's pages
                for i, page in enumerate(reader.pages):
                    if page == page_obj:
                        return i
            elif hasattr(reader, 'get_page_number'):
                return reader.get_page_number(page_ref)
    except Exception as e:
        print(f"[⚠] Could not determine page number: {e}")
    
    return None

def split_pdf_by_outline(pdf_path, output_dir, outline_items):
    """
    Split PDF based on outline/bookmark structure
    
    Args:
        pdf_path (Path): Input PDF path
        output_dir (Path): Output directory
        outline_items (list): Outline structure
    
    Returns:
        bool: Success status
    """
    reader = PdfReader(pdf_path)
    output_dir.mkdir(exist_ok=True)
    
    # Process outline items to get page ranges
    chapters = []
    
    for i, item in enumerate(outline_items):
        if item['level'] == 0:  # Top-level chapters only
            start_page = get_page_number_from_destination(reader, item['raw_item'])
            
            # Find end page (start of next chapter or end of document)
            end_page = len(reader.pages) - 1
            for j in range(i + 1, len(outline_items)):
                if outline_items[j]['level'] == 0:
                    next_start = get_page_number_from_destination(reader, outline_items[j]['raw_item'])
                    if next_start is not None:
                        end_page = next_start - 1
                        break
            
            if start_page is not None:
                # Clean title for filename
                clean_title = re.sub(r'[<>:"/\\|?*]', '_', item['title'])
                clean_title = clean_title.strip()
                
                chapters.append({
                    'title': clean_title,
                    'start_page': start_page,
                    'end_page': end_page,
                    'chapter_num': len(chapters) + 1
                })
    
    print(f"[*] Found {len(chapters)} chapters to extract")
    
    successful_extractions = 0
    
    # Create individual chapter PDFs
    for chapter in chapters:
        try:
            writer = PdfWriter()
            
            # Add pages for this chapter
            for page_num in range(chapter['start_page'], chapter['end_page'] + 1):
                if page_num < len(reader.pages):
                    writer.add_page(reader.pages[page_num])
            
            # Save chapter PDF
            chapter_filename = f"chapter_{chapter['chapter_num']:02d}_{chapter['title']}.pdf"
            chapter_path = output_dir / chapter_filename
            
            with open(chapter_path, 'wb') as output_file:
                writer.write(output_file)
            
            page_count = chapter['end_page'] - chapter['start_page'] + 1
            print(f"[✓] Created: {chapter_filename} ({page_count} pages)")
            successful_extractions += 1
            
        except Exception as e:
            print(f"[✗] Failed to create chapter '{chapter['title']}': {e}")
    
    return successful_extractions > 0

def detect_chapters_by_text(pdf_path, output_dir):
    """
    Attempt to detect chapters by analyzing text content
    
    Args:
        pdf_path (Path): Input PDF path
        output_dir (Path): Output directory
    
    Returns:
        bool: Success status
    """
    reader = PdfReader(pdf_path)
    output_dir.mkdir(exist_ok=True)
    
    print("[*] Analyzing text to detect chapter boundaries...")
    
    # Enhanced patterns for different chapter styles
    chapter_patterns = [
        (r'^\d{2}$', 'numbered_chapter'),  # "01", "02", etc. on their own line
        (r'^Chapter\s+\d+', 'chapter_word'),
        (r'^\d+\.\s+[A-Z]', 'numbered_title'),
        (r'^PART\s+\d+\)', 'part_heading'),  # "PART 1)", "PART 2)"
        (r'^[A-Z][A-Z\s&:-]{10,60}$', 'caps_title'),  # All caps titles (reasonable length)
    ]
    
    potential_chapters = []
    
    # First pass: find table of contents
    toc_pages = []
    for page_num in range(min(20, len(reader.pages))):  # Check first 20 pages for TOC
        try:
            text = reader.pages[page_num].extract_text()
            if 'CONTENTS' in text.upper() or 'TABLE OF CONTENTS' in text.upper():
                toc_pages.append(page_num)
                print(f"[*] Found table of contents on page {page_num + 1}")
        except:
            continue
    
    # Second pass: scan for chapter headings
    for page_num, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
            lines = text.split('\n')
            
            for line_num, line in enumerate(lines):
                line = line.strip()
                
                for pattern, pattern_type in chapter_patterns:
                    if re.match(pattern, line):
                        # Additional validation for numbered chapters
                        if pattern_type == 'numbered_chapter':
                            # Look for chapter title on next few lines
                            title_lines = []
                            for next_line in lines[line_num + 1:line_num + 5]:
                                next_line = next_line.strip()
                                if next_line and len(next_line) > 3:
                                    title_lines.append(next_line)
                            
                            if title_lines:
                                full_title = f"{line}: {' '.join(title_lines[:2])}"
                                potential_chapters.append({
                                    'title': full_title,
                                    'page': page_num,
                                    'line': line_num,
                                    'type': pattern_type,
                                    'number': int(line)
                                })
                        elif pattern_type == 'caps_title':
                            # Make sure it's not just random caps text
                            if any(word in line.lower() for word in ['poker', 'game', 'theory', 'strategy', 'play', 'bet', 'fold', 'raise']):
                                potential_chapters.append({
                                    'title': line,
                                    'page': page_num,
                                    'line': line_num,
                                    'type': pattern_type
                                })
                        else:
                            potential_chapters.append({
                                'title': line,
                                'page': page_num,
                                'line': line_num,
                                'type': pattern_type
                            })
                        break
        except Exception as e:
            print(f"[⚠] Could not extract text from page {page_num}: {e}")
    
    if not potential_chapters:
        print("[✗] No chapter headings detected in text")
        return False
    
    # Filter and sort chapters
    chapters = []
    
    # Prefer numbered chapters if we found them
    numbered_chapters = [ch for ch in potential_chapters if ch['type'] == 'numbered_chapter']
    if numbered_chapters:
        numbered_chapters.sort(key=lambda x: x['number'])
        chapters = numbered_chapters
        print(f"[*] Found {len(numbered_chapters)} numbered chapters")
    else:
        # Fall back to other chapter types
        other_chapters = [ch for ch in potential_chapters if ch['type'] != 'numbered_chapter']
        chapters = sorted(other_chapters, key=lambda x: x['page'])
        print(f"[*] Found {len(chapters)} potential chapters")
    
    print("[*] Detected chapters:")
    for i, chapter in enumerate(chapters[:15]):  # Show first 15
        print(f"  Page {chapter['page'] + 1:3d}: {chapter['title'][:60]}")
    
    if len(chapters) > 15:
        print(f"  ... and {len(chapters) - 15} more")
    
    # Ask user if they want to proceed with automatic splitting
    if len(chapters) > 1:
        print(f"\n[?] Found {len(chapters)} chapters. Proceed with automatic splitting? (y/n)")
        response = input().lower().strip()
        
        if response == 'y' or response == 'yes':
            return create_chapter_pdfs_from_detected(reader, chapters, output_dir)
        else:
            print("[*] Skipping automatic splitting. Manual review recommended.")
            return True
    else:
        print("[*] Not enough chapters detected for automatic splitting")
        return False

def create_chapter_pdfs_from_detected(reader, chapters, output_dir):
    """
    Create chapter PDFs from detected chapter boundaries
    
    Args:
        reader: PdfReader object
        chapters (list): Detected chapters
        output_dir (Path): Output directory
    
    Returns:
        bool: Success status
    """
    successful_extractions = 0
    
    for i, chapter in enumerate(chapters):
        try:
            writer = PdfWriter()
            
            # Determine page range
            start_page = chapter['page']
            if i < len(chapters) - 1:
                end_page = chapters[i + 1]['page'] - 1
            else:
                end_page = len(reader.pages) - 1
            
            # Add pages for this chapter
            for page_num in range(start_page, end_page + 1):
                if page_num < len(reader.pages):
                    writer.add_page(reader.pages[page_num])
            
            # Clean title for filename
            clean_title = re.sub(r'[<>:"/\\|?*]', '_', chapter['title'])
            clean_title = clean_title.replace(':', '').strip()[:50]  # Limit length
            
            chapter_filename = f"chapter_{i+1:02d}_{clean_title}.pdf"
            chapter_path = output_dir / chapter_filename
            
            with open(chapter_path, 'wb') as output_file:
                writer.write(output_file)
            
            page_count = end_page - start_page + 1
            file_size = chapter_path.stat().st_size / 1024  # KB
            print(f"[✓] Created: {chapter_filename} ({page_count} pages, {file_size:.1f}KB)")
            successful_extractions += 1
            
        except Exception as e:
            print(f"[✗] Failed to create chapter '{chapter['title']}': {e}")
    
    print(f"\n[✓] Successfully created {successful_extractions}/{len(chapters)} chapter PDFs")
    return successful_extractions > 0

def split_pdf_chapters(pdf_path, output_dir=None):
    """
    Main function to split PDF into chapters
    
    Args:
        pdf_path (str): Path to input PDF
        output_dir (str, optional): Output directory
    
    Returns:
        bool: Success status
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        print(f"[✗] PDF file not found: {pdf_path}")
        return False
    
    if output_dir is None:
        output_dir = pdf_path.parent / f"{pdf_path.stem}_chapters"
    else:
        output_dir = Path(output_dir)
    
    print(f"[*] Analyzing PDF: {pdf_path.name}")
    print(f"[*] Output directory: {output_dir}")
    
    # Analyze PDF structure
    analysis = analyze_pdf_structure(pdf_path)
    
    print(f"[*] PDF Info:")
    print(f"  Title: {analysis['title']}")
    print(f"  Pages: {analysis['total_pages']}")
    print(f"  Has outline: {analysis['has_outline']}")
    
    if analysis['has_outline'] and len(analysis['outline_items']) > 1:
        print(f"  Outline items: {len(analysis['outline_items'])}")
        
        # Show outline structure
        print("[*] Outline structure:")
        for item in analysis['outline_items'][:20]:  # Show first 20
            indent = "  " * (item['level'] + 1)
            print(f"{indent}{item['title']}")
        
        if len(analysis['outline_items']) > 20:
            print(f"  ... and {len(analysis['outline_items']) - 20} more items")
        
        # Try to split by outline
        return split_pdf_by_outline(pdf_path, output_dir, analysis['outline_items'])
    else:
        if analysis['has_outline']:
            print("[*] PDF has outline but insufficient chapter information")
        else:
            print("[*] No outline found")
        print("[*] Attempting text-based chapter detection...")
        return detect_chapters_by_text(pdf_path, output_dir)

def main():
    if len(sys.argv) < 2:
        print("Usage: python split_pdf_chapters.py <pdf_file> [output_directory]")
        print("Example: python split_pdf_chapters.py book.pdf chapters/")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = split_pdf_chapters(pdf_file, output_dir)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()