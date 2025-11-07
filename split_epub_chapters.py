#!/usr/bin/env python3
"""
EPUB Chapter to PDF Converter

This script extracts individual chapters from an EPUB file and converts each 
chapter to a separate PDF file using Calibre's ebook-convert tool.
"""

import subprocess
import sys
import os
import zipfile
import tempfile
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
import re

def extract_epub_chapters(epub_path, temp_dir):
    """
    Extract individual chapters from an EPUB file
    
    Args:
        epub_path (str): Path to input EPUB file
        temp_dir (str): Temporary directory for extraction
    
    Returns:
        list: List of chapter files and their titles
    """
    epub_path = Path(epub_path)
    chapters = []
    
    # Extract EPUB contents
    extract_dir = Path(temp_dir) / "epub_extract"
    extract_dir.mkdir(exist_ok=True)
    
    with zipfile.ZipFile(epub_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    
    print(f"[*] Extracted EPUB to {extract_dir}")
    
    # Find chapter files (look for XHTML files)
    chapter_files = []
    epub_dir = extract_dir / "EPUB"
    
    if epub_dir.exists():
        # Look for chapter files
        for file_path in epub_dir.glob("*.xhtml"):
            if "chap_" in file_path.name:
                chapter_files.append(file_path)
    
    # Sort chapter files by name
    chapter_files.sort(key=lambda x: x.name)
    
    print(f"[*] Found {len(chapter_files)} chapter files")
    
    # Extract chapter titles and prepare individual EPUBs
    for i, chapter_file in enumerate(chapter_files):
        try:
            # Read chapter content
            with open(chapter_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract title from the chapter
            title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()
            else:
                title = f"Chapter {i+1}"
            
            # Clean title for filename
            clean_title = re.sub(r'[<>:"/\\|?*]', '_', title)
            clean_title = clean_title.replace('&amp;', 'and').replace('&', 'and')
            
            chapters.append({
                'file': chapter_file,
                'title': title,
                'clean_title': clean_title,
                'number': i + 1
            })
            
        except Exception as e:
            print(f"[⚠] Warning: Could not process {chapter_file.name}: {e}")
    
    return chapters, extract_dir

def identify_front_matter_chapters(chapters):
    """
    Identify which chapters should be grouped as front matter
    
    Args:
        chapters (list): List of chapter information
    
    Returns:
        tuple: (front_matter_chapters, main_chapters)
    """
    front_matter_keywords = [
        'about the author', 'title page', 'copyright', 'contents', 
        'foreword', 'introduction', 'preface', 'acknowledgments',
        'dedication', 'table of contents', 'toc'
    ]
    
    # Strategy book keywords that should be treated as main chapters
    strategy_keywords = [
        'play to learn', 'table selection', 'bankroll management', 'math is easy',
        'pre-flop', 'post-flop', '3-betting', '4-betting', 'adjusting against',
        'balancing your range', 'multi-way pots', 'scare cards', 'timing tells',
        'final words'
    ]
    
    front_matter = []
    main_chapters = []
    
    # Look for numbered chapters (like "1)", "Chapter 1", etc.) to determine where main content starts
    main_content_started = False
    
    for chapter in chapters:
        title_lower = chapter['title'].lower()
        
        # Check if this looks like a numbered chapter/game
        is_numbered_chapter = (
            re.search(r'^\d+\)', chapter['title']) or  # "1) Game Name"
            re.search(r'^chapter\s+\d+', title_lower) or  # "Chapter 1"
            re.search(r'^\d+\.', chapter['title'])  # "1. Game Name"
        )
        
        # Check if this is a strategy book main section
        is_strategy_chapter = any(keyword in title_lower for keyword in strategy_keywords)
        
        # If we hit a numbered chapter or strategy chapter, everything from here on is main content
        if is_numbered_chapter or is_strategy_chapter:
            main_content_started = True
        
        # Special case: Glossary goes with main content even though it's not numbered
        is_glossary = 'glossary' in title_lower
        
        if main_content_started or is_glossary:
            main_chapters.append(chapter)
        else:
            # Check if it's typical front matter
            is_front_matter = any(keyword in title_lower for keyword in front_matter_keywords)
            if is_front_matter or not main_content_started:
                front_matter.append(chapter)
            else:
                main_chapters.append(chapter)
    
    return front_matter, main_chapters

def create_combined_epub(chapters, title, extract_dir, output_dir, filename_prefix):
    """
    Create a combined EPUB from multiple chapters
    
    Args:
        chapters (list): List of chapter information to combine
        title (str): Title for the combined EPUB
        extract_dir (Path): Directory with extracted EPUB contents
        output_dir (Path): Output directory for EPUB
        filename_prefix (str): Prefix for the EPUB filename
    
    Returns:
        Path: Path to created combined EPUB
    """
    if not chapters:
        return None
        
    combined_epub_dir = output_dir / f"{filename_prefix}_epub"
    combined_epub_dir.mkdir(exist_ok=True)
    
    # Copy EPUB structure
    epub_source = extract_dir / "EPUB"
    combined_epub_content = combined_epub_dir / "EPUB"
    
    # Copy necessary files
    shutil.copytree(epub_source / "style", combined_epub_content / "style", dirs_exist_ok=True)
    
    # Copy META-INF
    shutil.copytree(extract_dir / "META-INF", combined_epub_dir / "META-INF", dirs_exist_ok=True)
    
    # Copy mimetype
    shutil.copy2(extract_dir / "mimetype", combined_epub_dir / "mimetype")
    
    # Combine all chapter contents
    combined_content = '<?xml version="1.0" encoding="utf-8"?>\n'
    combined_content += '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
    combined_content += '<html xmlns="http://www.w3.org/1999/xhtml">\n<head>\n'
    combined_content += f'<title>{title}</title>\n'
    combined_content += '<link rel="stylesheet" type="text/css" href="style/default.css"/>\n'
    combined_content += '</head>\n<body>\n'
    
    for i, chapter in enumerate(chapters):
        try:
            # Read chapter content
            with open(chapter['file'], 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract body content (remove html/head tags)
            body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
            if body_match:
                body_content = body_match.group(1)
                
                # Add chapter separator if not the first chapter
                if i > 0:
                    combined_content += '<div style="page-break-before: always;"></div>\n'
                
                combined_content += body_content + '\n'
            
        except Exception as e:
            print(f"[⚠] Warning: Could not include chapter {chapter['title']}: {e}")
    
    combined_content += '</body>\n</html>'
    
    # Write combined content
    with open(combined_epub_content / "combined.xhtml", 'w', encoding='utf-8') as f:
        f.write(combined_content)
    
    # Create content.opf for combined chapters
    content_opf = f"""<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
  <metadata xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:opf="http://www.idpf.org/2007/opf" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <dc:title>{title}</dc:title>
    <dc:creator>Combined Chapters</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier id="uuid_id">{filename_prefix}</dc:identifier>
  </metadata>
  <manifest>
    <item href="combined.xhtml" id="combined" media-type="application/xhtml+xml"/>
    <item href="style/default.css" id="css" media-type="text/css"/>
  </manifest>
  <spine>
    <itemref idref="combined"/>
  </spine>
</package>"""
    
    with open(combined_epub_content / "content.opf", 'w', encoding='utf-8') as f:
        f.write(content_opf)
    
    # Create the EPUB file
    combined_epub_path = output_dir / f"{filename_prefix}.epub"
    
    with zipfile.ZipFile(combined_epub_path, 'w', zipfile.ZIP_DEFLATED) as epub_zip:
        # Add mimetype first (uncompressed)
        epub_zip.write(combined_epub_dir / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
        
        # Add other files
        for root, dirs, files in os.walk(combined_epub_dir):
            for file in files:
                if file == "mimetype":
                    continue
                file_path = Path(root) / file
                arc_path = file_path.relative_to(combined_epub_dir)
                epub_zip.write(file_path, arc_path)
    
    # Clean up temporary directory
    shutil.rmtree(combined_epub_dir)
    
    return combined_epub_path

def create_chapter_epub(chapter_info, extract_dir, output_dir):
    """
    Create a standalone EPUB for a single chapter
    
    Args:
        chapter_info (dict): Chapter information
        extract_dir (Path): Directory with extracted EPUB contents
        output_dir (Path): Output directory for chapter EPUB
    
    Returns:
        Path: Path to created chapter EPUB
    """
    chapter_epub_dir = output_dir / f"chapter_{chapter_info['number']:02d}_epub"
    chapter_epub_dir.mkdir(exist_ok=True)
    
    # Copy EPUB structure
    epub_source = extract_dir / "EPUB"
    chapter_epub_content = chapter_epub_dir / "EPUB"
    
    # Copy necessary files
    shutil.copytree(epub_source / "style", chapter_epub_content / "style", dirs_exist_ok=True)
    
    # Copy META-INF
    shutil.copytree(extract_dir / "META-INF", chapter_epub_dir / "META-INF", dirs_exist_ok=True)
    
    # Copy mimetype
    shutil.copy2(extract_dir / "mimetype", chapter_epub_dir / "mimetype")
    
    # Copy the specific chapter file
    shutil.copy2(chapter_info['file'], chapter_epub_content / "chapter.xhtml")
    
    # Create a simple content.opf for the chapter
    content_opf = f"""<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
  <metadata xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:opf="http://www.idpf.org/2007/opf" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <dc:title>{chapter_info['title']}</dc:title>
    <dc:creator>Chapter Extract</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier id="uuid_id">chapter_{chapter_info['number']}</dc:identifier>
  </metadata>
  <manifest>
    <item href="chapter.xhtml" id="chapter" media-type="application/xhtml+xml"/>
    <item href="style/default.css" id="css" media-type="text/css"/>
  </manifest>
  <spine>
    <itemref idref="chapter"/>
  </spine>
</package>"""
    
    with open(chapter_epub_content / "content.opf", 'w', encoding='utf-8') as f:
        f.write(content_opf)
    
    # Create the EPUB file
    chapter_epub_path = output_dir / f"chapter_{chapter_info['number']:02d}_{chapter_info['clean_title']}.epub"
    
    with zipfile.ZipFile(chapter_epub_path, 'w', zipfile.ZIP_DEFLATED) as epub_zip:
        # Add mimetype first (uncompressed)
        epub_zip.write(chapter_epub_dir / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
        
        # Add other files
        for root, dirs, files in os.walk(chapter_epub_dir):
            for file in files:
                if file == "mimetype":
                    continue
                file_path = Path(root) / file
                arc_path = file_path.relative_to(chapter_epub_dir)
                epub_zip.write(file_path, arc_path)
    
    # Clean up temporary directory
    shutil.rmtree(chapter_epub_dir)
    
    return chapter_epub_path
    """
    Create a standalone EPUB for a single chapter
    
    Args:
        chapter_info (dict): Chapter information
        extract_dir (Path): Directory with extracted EPUB contents
        output_dir (Path): Output directory for chapter EPUB
    
    Returns:
        Path: Path to created chapter EPUB
    """
    chapter_epub_dir = output_dir / f"chapter_{chapter_info['number']:02d}_epub"
    chapter_epub_dir.mkdir(exist_ok=True)
    
    # Copy EPUB structure
    epub_source = extract_dir / "EPUB"
    chapter_epub_content = chapter_epub_dir / "EPUB"
    
    # Copy necessary files
    shutil.copytree(epub_source / "style", chapter_epub_content / "style", dirs_exist_ok=True)
    
    # Copy META-INF
    shutil.copytree(extract_dir / "META-INF", chapter_epub_dir / "META-INF", dirs_exist_ok=True)
    
    # Copy mimetype
    shutil.copy2(extract_dir / "mimetype", chapter_epub_dir / "mimetype")
    
    # Copy the specific chapter file
    shutil.copy2(chapter_info['file'], chapter_epub_content / "chapter.xhtml")
    
    # Create a simple content.opf for the chapter
    content_opf = f"""<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
  <metadata xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:opf="http://www.idpf.org/2007/opf" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <dc:title>{chapter_info['title']}</dc:title>
    <dc:creator>Chapter Extract</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier id="uuid_id">chapter_{chapter_info['number']}</dc:identifier>
  </metadata>
  <manifest>
    <item href="chapter.xhtml" id="chapter" media-type="application/xhtml+xml"/>
    <item href="style/default.css" id="css" media-type="text/css"/>
  </manifest>
  <spine>
    <itemref idref="chapter"/>
  </spine>
</package>"""
    
    with open(chapter_epub_content / "content.opf", 'w', encoding='utf-8') as f:
        f.write(content_opf)
    
    # Create the EPUB file
    chapter_epub_path = output_dir / f"chapter_{chapter_info['number']:02d}_{chapter_info['clean_title']}.epub"
    
    with zipfile.ZipFile(chapter_epub_path, 'w', zipfile.ZIP_DEFLATED) as epub_zip:
        # Add mimetype first (uncompressed)
        epub_zip.write(chapter_epub_dir / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
        
        # Add other files
        for root, dirs, files in os.walk(chapter_epub_dir):
            for file in files:
                if file == "mimetype":
                    continue
                file_path = Path(root) / file
                arc_path = file_path.relative_to(chapter_epub_dir)
                epub_zip.write(file_path, arc_path)
    
    # Clean up temporary directory
    shutil.rmtree(chapter_epub_dir)
    
    return chapter_epub_path

def convert_epub_to_pdf(epub_path, pdf_path):
    """
    Convert a single EPUB to PDF using Calibre
    
    Args:
        epub_path (Path): Path to EPUB file
        pdf_path (Path): Path for output PDF
    
    Returns:
        bool: True if successful
    """
    cmd = [
        'ebook-convert', 
        str(epub_path), 
        str(pdf_path),
        '--paper-size', 'a4',
        '--pdf-page-margin-left', '36',
        '--pdf-page-margin-right', '36',
        '--pdf-page-margin-top', '36',
        '--pdf-page-margin-bottom', '36',
        '--pdf-default-font-size', '12'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[✗] Conversion failed for {epub_path.name}: {e}")
        return False

def split_epub_to_chapter_pdfs(epub_path, output_dir=None):
    """
    Main function to split EPUB into chapter PDFs with front matter grouping
    
    Args:
        epub_path (str): Path to input EPUB file
        output_dir (str, optional): Output directory. Defaults to 'chapters' subdirectory
    
    Returns:
        bool: True if successful
    """
    epub_path = Path(epub_path)
    
    if not epub_path.exists():
        print(f"[✗] Error: EPUB file not found: {epub_path}")
        return False
    
    if output_dir is None:
        output_dir = epub_path.parent / "chapters"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(exist_ok=True)
    
    print(f"[*] Splitting {epub_path.name} into chapter PDFs with grouped front matter...")
    print(f"[*] Output directory: {output_dir}")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Extract chapters from EPUB
        chapters, extract_dir = extract_epub_chapters(epub_path, temp_dir)
        
        if not chapters:
            print("[✗] No chapters found in EPUB file")
            return False
        
        # Group chapters into front matter and main content
        front_matter, main_chapters = identify_front_matter_chapters(chapters)
        
        print(f"[*] Found {len(front_matter)} front matter chapters and {len(main_chapters)} main chapters")
        
        successful_conversions = 0
        
        # First, create a complete book PDF from the original EPUB
        print(f"[*] Creating complete book PDF...")
        try:
            complete_book_pdf = output_dir / "00_Complete_Book.pdf"
            if convert_epub_to_pdf(epub_path, complete_book_pdf):
                print(f"[✓] Created: 00_Complete_Book.pdf")
                successful_conversions += 1
            else:
                print(f"[✗] Failed to create complete book PDF")
        except Exception as e:
            print(f"[✗] Error creating complete book PDF: {e}")
        
        # Process front matter as a single combined PDF
        if front_matter:
            print(f"[*] Processing Front Matter ({len(front_matter)} chapters): {', '.join([ch['title'] for ch in front_matter])}")
            
            try:
                # Create combined front matter EPUB
                front_matter_epub = create_combined_epub(
                    front_matter, 
                    "Front Matter", 
                    extract_dir, 
                    Path(temp_dir),
                    "00_front_matter"
                )
                
                if front_matter_epub:
                    # Convert to PDF
                    front_matter_pdf = output_dir / "00_Front_Matter.pdf"
                    
                    if convert_epub_to_pdf(front_matter_epub, front_matter_pdf):
                        print(f"[✓] Created: 00_Front_Matter.pdf")
                        successful_conversions += 1
                    else:
                        print(f"[✗] Failed to convert front matter")
                    
                    # Clean up
                    front_matter_epub.unlink(missing_ok=True)
                
            except Exception as e:
                print(f"[✗] Error processing front matter: {e}")
        
        # Process each main chapter individually
        for i, chapter_info in enumerate(main_chapters):
            # Renumber for output (front matter takes position 00)
            chapter_num = i + 1
            print(f"[*] Processing Chapter {chapter_num}: {chapter_info['title']}")
            
            try:
                # Create individual chapter EPUB
                chapter_epub_path = create_chapter_epub(chapter_info, extract_dir, Path(temp_dir))
                
                # Convert to PDF
                pdf_filename = f"chapter_{chapter_num:02d}_{chapter_info['clean_title']}.pdf"
                chapter_pdf_path = output_dir / pdf_filename
                
                if convert_epub_to_pdf(chapter_epub_path, chapter_pdf_path):
                    print(f"[✓] Created: {pdf_filename}")
                    successful_conversions += 1
                else:
                    print(f"[✗] Failed to convert: {chapter_info['title']}")
                
                # Clean up chapter EPUB
                chapter_epub_path.unlink(missing_ok=True)
                
            except Exception as e:
                print(f"[✗] Error processing chapter {chapter_info['title']}: {e}")
        
        total_expected = 1 + (1 if front_matter else 0) + len(main_chapters)  # +1 for complete book
        print(f"\n[✓] Conversion complete!")
        print(f"[*] Successfully converted {successful_conversions}/{total_expected} items")
        print(f"[*] Chapter PDFs saved to: {output_dir}")
        
        return successful_conversions > 0

def main():
    if len(sys.argv) < 2:
        print("Usage: python split_epub_chapters.py <epub_file> [output_directory]")
        print("Example: python split_epub_chapters.py decoded_book.epub chapters/")
        sys.exit(1)
    
    epub_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = split_epub_to_chapter_pdfs(epub_file, output_dir)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()