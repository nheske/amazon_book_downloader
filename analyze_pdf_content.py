#!/usr/bin/env python3
"""
PDF Content Analyzer - Check first few pages to understand structure
"""

import sys
from pathlib import Path
from PyPDF2 import PdfReader

def analyze_pdf_content(pdf_path, pages_to_check=10):
    """Analyze first few pages of PDF to understand structure"""
    
    reader = PdfReader(pdf_path)
    
    print(f"[*] Analyzing first {pages_to_check} pages of {pdf_path.name}")
    print(f"[*] Total pages: {len(reader.pages)}")
    print("="*80)
    
    for i in range(min(pages_to_check, len(reader.pages))):
        try:
            page = reader.pages[i]
            text = page.extract_text()
            
            print(f"\nPAGE {i+1}:")
            print("-" * 40)
            
            # Show first 20 lines of each page
            lines = text.split('\n')
            for j, line in enumerate(lines[:20]):
                line = line.strip()
                if line:  # Only show non-empty lines
                    print(f"{j+1:2d}: {line}")
            
            if len(lines) > 20:
                print(f"... ({len(lines) - 20} more lines)")
                
        except Exception as e:
            print(f"[✗] Could not extract text from page {i+1}: {e}")
    
    print("="*80)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_pdf_content.py <pdf_file>")
        sys.exit(1)
    
    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"[✗] PDF file not found: {pdf_path}")
        sys.exit(1)
    
    analyze_pdf_content(pdf_path)