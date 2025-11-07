#!/usr/bin/env python3
"""
Manual chapter mapping for Modern Poker Theory based on the book structure
"""

import sys
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter

def get_modern_poker_chapters():
    """
    Manual mapping of Modern Poker Theory chapters based on the actual book structure
    """
    return [
        {'number': 1, 'title': 'Poker Fundamentals', 'start_page': 18},
        {'number': 2, 'title': 'The Elements of Game Theory', 'start_page': 84}, 
        {'number': 3, 'title': 'Modern Poker Software', 'start_page': 148},
        {'number': 4, 'title': 'The Theory of Pre-flop Play', 'start_page': 150},
        {'number': 5, 'title': '6-max Cash Game Equilibrium Strategies', 'start_page': 180},
        {'number': 6, 'title': 'The Theory of Tournament Play', 'start_page': 250},
        {'number': 7, 'title': 'MTT Equilibrium Strategies - Playing First In', 'start_page': 293},
        {'number': 8, 'title': 'MTT Equilibrium Strategies - Defense', 'start_page': 360},
        {'number': 9, 'title': 'MTT Equilibrium Strategies - Playing Versus 3-bets', 'start_page': 513},
        {'number': 10, 'title': 'The Theory of Post-flop Play', 'start_page': 589},
        {'number': 11, 'title': 'The Theory of Flop Play', 'start_page': 624},
        {'number': 12, 'title': 'The Flop Continuation-bet', 'start_page': 650},
        {'number': 13, 'title': 'GTO Turn Strategies', 'start_page': 748},
        {'number': 14, 'title': 'GTO River Strategies', 'start_page': 779},
    ]

def verify_chapters(pdf_path, chapters):
    """
    Verify the chapter start pages by checking the content
    """
    reader = PdfReader(pdf_path)
    verified_chapters = []
    
    print("[*] Verifying chapter start pages...")
    
    for chapter in chapters:
        start_page = chapter['start_page']
        
        if start_page >= len(reader.pages):
            print(f"[⚠] Chapter {chapter['number']} start page {start_page} is beyond book length")
            continue
            
        try:
            # Check the page content around the start page
            page_text = reader.pages[start_page].extract_text()
            
            # Look for chapter indicators
            has_chapter_marker = False
            lines = page_text.split('\n')[:20]  # First 20 lines
            
            for line in lines:
                line = line.strip().upper()
                # Look for the chapter number or title
                if (f"{chapter['number']:02d}" in line or 
                    any(word in line for word in chapter['title'].upper().split()[:3])):
                    has_chapter_marker = True
                    break
            
            if has_chapter_marker:
                print(f"[✓] Chapter {chapter['number']:02d}: {chapter['title']} (page {start_page + 1})")
                verified_chapters.append(chapter)
            else:
                print(f"[⚠] Chapter {chapter['number']:02d}: Could not verify on page {start_page + 1}")
                # Still include it, might be a formatting issue
                verified_chapters.append(chapter)
                
        except Exception as e:
            print(f"[✗] Error checking chapter {chapter['number']}: {e}")
            
    return verified_chapters

def create_manual_chapter_pdfs(pdf_path, output_dir, chapters):
    """
    Create chapter PDFs using manual page ranges
    """
    reader = PdfReader(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    successful = 0
    
    for i, chapter in enumerate(chapters):
        try:
            writer = PdfWriter()
            
            # Determine page range
            start_page = chapter['start_page']
            
            # End page is start of next chapter minus 1, or end of book
            if i < len(chapters) - 1:
                end_page = chapters[i + 1]['start_page'] - 1
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
                clean_title = chapter['title'].replace('/', '_').replace(':', '_')
                filename = f"chapter_{chapter['number']:02d}_{clean_title}.pdf"
                output_path = output_dir / filename
                
                with open(output_path, 'wb') as output_file:
                    writer.write(output_file)
                
                file_size = output_path.stat().st_size / 1024  # KB
                print(f"[✓] Chapter {chapter['number']:02d}: {filename} ({page_count} pages, {file_size:.0f}KB)")
                successful += 1
            else:
                print(f"[✗] Chapter {chapter['number']:02d}: No pages to extract")
                
        except Exception as e:
            print(f"[✗] Failed to create chapter {chapter['number']:02d}: {e}")
    
    return successful

def main():
    if len(sys.argv) < 2:
        print("Usage: python manual_chapter_split.py <pdf_file> [output_dir]")
        sys.exit(1)
    
    pdf_path = Path(sys.argv[1])
    output_dir = sys.argv[2] if len(sys.argv) > 2 else f"output/{pdf_path.stem}_manual_chapters"
    
    if not pdf_path.exists():
        print(f"[✗] PDF not found: {pdf_path}")
        sys.exit(1)
    
    print(f"[*] Processing: {pdf_path.name}")
    print(f"[*] Output directory: {output_dir}")
    
    # Get predefined chapter structure
    chapters = get_modern_poker_chapters()
    
    # Verify the chapters
    verified_chapters = verify_chapters(pdf_path, chapters)
    
    if not verified_chapters:
        print("[✗] No chapters verified")
        sys.exit(1)
    
    print(f"\n[*] Creating {len(verified_chapters)} chapter PDFs...")
    
    # Create the PDFs
    successful = create_manual_chapter_pdfs(pdf_path, output_dir, verified_chapters)
    
    if successful:
        print(f"\n[✓] Successfully created {successful} chapter PDFs")
        print(f"[*] Output directory: {output_dir}")
    else:
        print(f"\n[✗] Failed to create chapter PDFs")

if __name__ == "__main__":
    main()