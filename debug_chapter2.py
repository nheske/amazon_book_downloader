#!/usr/bin/env python3
"""
Debug chapter detection - specifically look for Chapter 2
"""

import sys
from pathlib import Path
from PyPDF2 import PdfReader

def debug_chapter_2(pdf_path):
    """Debug what's happening around page 84 where Chapter 2 should be"""
    
    reader = PdfReader(pdf_path)
    
    print("Looking for Chapter 2 around page 84...")
    
    # Check pages 80-90
    for page_num in range(79, min(90, len(reader.pages))):
        try:
            text = reader.pages[page_num].extract_text()
            lines = text.split('\n')
            
            # Look for "02" or "THE ELEMENTS OF GAME THEORY"
            for i, line in enumerate(lines):
                line = line.strip()
                if line == "02" or "ELEMENTS OF GAME THEORY" in line.upper():
                    print(f"\nPage {page_num + 1}:")
                    print(f"Line {i}: '{line}'")
                    
                    # Show context around this line
                    start = max(0, i - 3)
                    end = min(len(lines), i + 6)
                    for j in range(start, end):
                        marker = ">>> " if j == i else "    "
                        print(f"{marker}{j:2d}: {lines[j].strip()}")
                        
        except Exception as e:
            print(f"Error on page {page_num + 1}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_chapter2.py <pdf_file>")
        sys.exit(1)
    
    debug_chapter_2(Path(sys.argv[1]))