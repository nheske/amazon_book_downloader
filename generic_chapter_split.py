#!/usr/bin/env python3
"""
Generic PDF chapter splitter with manual chapter definitions
"""

import sys
import json
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter

# Predefined chapter mappings for known books
KNOWN_BOOKS = {
    "modern_poker_theory": {
        "patterns": ["modern poker theory", "acevedo"],
        "chapters": [
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
    },
    "expert_heads_up_volume2": {
        "patterns": ["volume 2", "multiple streets"],
        "chapters": [
            {'number': 9, 'title': 'Preliminaries', 'start_page': 13},
            {'number': 10, 'title': 'Turn Play - Polar Versus Bluff-catchers Redux', 'start_page': 50},
            {'number': 11, 'title': 'Nearly Static, Nearly PvBC Turn Play', 'start_page': 107},
            {'number': 12, 'title': 'Initiative and Less Common Turn Lines', 'start_page': 144},
            {'number': 13, 'title': 'Turn Play - Volatile Boards and Capture Factors', 'start_page': 194},
            {'number': 14, 'title': 'Flop Play and the C-bet Dynamic', 'start_page': 242},
            {'number': 15, 'title': 'Pre-Flop Play', 'start_page': 326},
            {'number': 16, 'title': 'Win-rate-maximizing Play', 'start_page': 371},
            {'number': 17, 'title': 'Putting it all Together', 'start_page': 390},
        ]
    },
    "expert_heads_up": {
        "patterns": ["expert heads up", "heads up no limit", "hunl"],
        "chapters": [
            {'number': 1, 'title': 'Introduction to HUNL Strategy', 'start_page': 13},
            {'number': 2, 'title': 'Game-theoretic Strategies', 'start_page': 26},
            {'number': 3, 'title': 'Preflop-only Games', 'start_page': 74},
            {'number': 4, 'title': 'The Indifference Principle', 'start_page': 109},
            {'number': 5, 'title': 'Equity Distributions', 'start_page': 133},
            {'number': 6, 'title': 'Postflop Concepts', 'start_page': 153},
            {'number': 7, 'title': 'River Play', 'start_page': 194},
            {'number': 8, 'title': 'Epilogue to Volume I', 'start_page': 326},
        ]
    },
    # Add more books here as needed
    "example_book": {
        "patterns": ["example", "sample book"],
        "chapters": [
            {'number': 1, 'title': 'Introduction', 'start_page': 10},
            {'number': 2, 'title': 'Getting Started', 'start_page': 25},
            # ... more chapters
        ]
    }
}

def identify_book(pdf_path):
    """
    Try to identify which book this is based on filename or content
    """
    filename = Path(pdf_path).name.lower()
    
    for book_id, book_info in KNOWN_BOOKS.items():
        for pattern in book_info["patterns"]:
            if pattern.lower() in filename:
                print(f"[✓] Identified book: {book_id}")
                return book_id, book_info["chapters"]
    
    return None, None

def load_custom_chapters(chapters_file):
    """
    Load chapter definitions from a JSON file
    """
    try:
        with open(chapters_file, 'r') as f:
            data = json.load(f)
        
        # Validate structure
        if not isinstance(data, list):
            print("[✗] Chapters file must contain a list of chapters")
            return None
        
        for chapter in data:
            required_fields = ['number', 'title', 'start_page']
            if not all(field in chapter for field in required_fields):
                print(f"[✗] Chapter missing required fields: {required_fields}")
                return None
        
        print(f"[✓] Loaded {len(data)} chapters from {chapters_file}")
        return data
        
    except json.JSONDecodeError as e:
        print(f"[✗] Invalid JSON in chapters file: {e}")
    except FileNotFoundError:
        print(f"[✗] Chapters file not found: {chapters_file}")
    except Exception as e:
        print(f"[✗] Error loading chapters file: {e}")
    
    return None

def create_chapters_template(output_file):
    """
    Create a template chapters.json file for manual editing
    """
    template = [
        {
            "number": 1,
            "title": "Chapter 1 Title",
            "start_page": 10,
            "notes": "Page numbers are 0-based (first page = 0)"
        },
        {
            "number": 2,
            "title": "Chapter 2 Title", 
            "start_page": 25
        },
        {
            "number": 3,
            "title": "Chapter 3 Title",
            "start_page": 45
        }
    ]
    
    try:
        with open(output_file, 'w') as f:
            json.dump(template, f, indent=2)
        
        print(f"[✓] Created template chapters file: {output_file}")
        print(f"[*] Edit this file with your book's actual chapter structure")
        print(f"[*] Then run: python {sys.argv[0]} <pdf_file> --chapters {output_file}")
        return True
        
    except Exception as e:
        print(f"[✗] Failed to create template: {e}")
        return False

def create_chapter_pdfs(pdf_path, output_dir, chapters):
    """
    Create chapter PDFs from chapter definitions
    """
    reader = PdfReader(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    successful = 0
    total_pages = len(reader.pages)
    
    print(f"[*] PDF has {total_pages} pages")
    print(f"[*] Creating {len(chapters)} chapter PDFs...")
    
    for i, chapter in enumerate(chapters):
        try:
            writer = PdfWriter()
            
            # Determine page range
            start_page = chapter['start_page']
            
            # End page is start of next chapter minus 1, or end of book
            if i < len(chapters) - 1:
                end_page = chapters[i + 1]['start_page'] - 1
            else:
                end_page = total_pages - 1
            
            # Validate page range
            if start_page >= total_pages:
                print(f"[⚠] Chapter {chapter['number']:02d}: Start page {start_page} beyond book ({total_pages} pages)")
                continue
                
            # Add pages
            page_count = 0
            for page_num in range(start_page, min(end_page + 1, total_pages)):
                writer.add_page(reader.pages[page_num])
                page_count += 1
            
            if page_count > 0:
                # Clean title for filename
                clean_title = chapter['title'].replace('/', '_').replace(':', '_').replace('\\', '_')
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
        print("Generic PDF Chapter Splitter")
        print("")
        print("Usage:")
        print(f"  {sys.argv[0]} <pdf_file>                    # Auto-detect known books")
        print(f"  {sys.argv[0]} <pdf_file> --chapters <file>  # Use custom chapter definitions")
        print(f"  {sys.argv[0]} --template <file>             # Create chapters template")
        print("")
        print("Examples:")
        print(f"  {sys.argv[0]} book.pdf")
        print(f"  {sys.argv[0]} book.pdf --chapters chapters.json")
        print(f"  {sys.argv[0]} --template my_chapters.json")
        sys.exit(1)
    
    # Handle template creation
    if sys.argv[1] == '--template':
        if len(sys.argv) < 3:
            print("[✗] Please specify output file for template")
            sys.exit(1)
        create_chapters_template(sys.argv[2])
        sys.exit(0)
    
    pdf_path = Path(sys.argv[1])
    
    if not pdf_path.exists():
        print(f"[✗] PDF not found: {pdf_path}")
        sys.exit(1)
    
    # Check for custom chapters file
    chapters = None
    if len(sys.argv) >= 4 and sys.argv[2] == '--chapters':
        chapters_file = sys.argv[3]
        chapters = load_custom_chapters(chapters_file)
        if not chapters:
            sys.exit(1)
    else:
        # Try to auto-detect book
        book_id, chapters = identify_book(pdf_path)
        if not chapters:
            print(f"[⚠] Book not recognized: {pdf_path.name}")
            print(f"[*] Create a chapters file with: {sys.argv[0]} --template chapters.json")
            print(f"[*] Then use: {sys.argv[0]} \"{pdf_path}\" --chapters chapters.json")
            sys.exit(1)
    
    # Set output directory
    output_dir = f"pdfs/output/{pdf_path.stem}_chapters"
    
    print(f"[*] Processing: {pdf_path.name}")
    print(f"[*] Output directory: {output_dir}")
    
    # Create the chapter PDFs
    successful = create_chapter_pdfs(pdf_path, output_dir, chapters)
    
    if successful:
        print(f"\n[✓] Successfully created {successful} chapter PDFs")
        print(f"[*] Output directory: {output_dir}")
    else:
        print(f"\n[✗] Failed to create chapter PDFs")

if __name__ == "__main__":
    main()