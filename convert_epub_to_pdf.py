#!/usr/bin/env python3
"""
EPUB to PDF Converter using Calibre

This script converts EPUB files to PDF format using Calibre's ebook-convert tool.
Provides options for customizing the PDF output format and quality.
"""

import subprocess
import sys
import os
from pathlib import Path

def convert_epub_to_pdf(epub_path, pdf_path=None, options=None):
    """
    Convert EPUB to PDF using Calibre's ebook-convert
    
    Args:
        epub_path (str): Path to input EPUB file
        pdf_path (str, optional): Path for output PDF file. If None, uses same name with .pdf extension
        options (dict, optional): Additional conversion options
    
    Returns:
        bool: True if conversion successful, False otherwise
    """
    epub_path = Path(epub_path)
    
    if not epub_path.exists():
        print(f"[✗] Error: EPUB file not found: {epub_path}")
        return False
    
    if pdf_path is None:
        pdf_path = epub_path.with_suffix('.pdf')
    else:
        pdf_path = Path(pdf_path)
    
    # Default conversion options for better PDF quality
    default_options = {
        '--paper-size': 'a4',
        '--pdf-page-margin-left': '36',
        '--pdf-page-margin-right': '36', 
        '--pdf-page-margin-top': '36',
        '--pdf-page-margin-bottom': '36',
        '--pdf-default-font-size': '12',
        '--pdf-serif-family': 'Times New Roman',
        '--pdf-sans-family': 'Arial'
    }
    
    # Merge user options with defaults
    if options:
        default_options.update(options)
    
    # Build command
    cmd = ['ebook-convert', str(epub_path), str(pdf_path)]
    
    # Add options to command
    for key, value in default_options.items():
        if value is None:
            cmd.append(key)
        else:
            cmd.extend([key, str(value)])
    
    print(f"[*] Converting {epub_path.name} to PDF...")
    print(f"[*] Output: {pdf_path}")
    print(f"[*] Command: {' '.join(cmd[:3])} [+ {len(cmd)-3} options]")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"[✓] Conversion successful!")
        print(f"[✓] PDF created: {pdf_path}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"[✗] Conversion failed!")
        print(f"[✗] Error: {e}")
        if e.stderr:
            print(f"[✗] Details: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"[✗] Error: ebook-convert not found. Please install Calibre.")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_epub_to_pdf.py <epub_file> [pdf_file]")
        print("Example: python convert_epub_to_pdf.py decoded_book.epub my_book.pdf")
        sys.exit(1)
    
    epub_file = sys.argv[1]
    pdf_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = convert_epub_to_pdf(epub_file, pdf_file)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()