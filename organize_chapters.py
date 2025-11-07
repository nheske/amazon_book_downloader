#!/usr/bin/env python3
"""
Organize and clean up PDF chapter outputs
"""

import sys
import shutil
from pathlib import Path

def organize_chapters(base_dir="pdfs/output"):
    """
    Organize chapter output directories and remove duplicates
    """
    base_path = Path(base_dir)
    if not base_path.exists():
        print(f"[✗] Output directory not found: {base_dir}")
        return
    
    print(f"[*] Organizing chapters in: {base_dir}")
    
    # Find all chapter directories
    chapter_dirs = []
    for item in base_path.iterdir():
        if item.is_dir() and "chapter" in item.name.lower():
            chapter_dirs.append(item)
    
    if not chapter_dirs:
        print("[⚠] No chapter directories found")
        return
    
    # Group by book
    books = {}
    for dir_path in chapter_dirs:
        # Extract book name from directory
        dir_name = dir_path.name
        if "_chapters" in dir_name:
            book_name = dir_name.replace("_chapters", "")
        elif "_manual_chapters" in dir_name:
            book_name = dir_name.replace("_manual_chapters", "")
        elif "_smart_chapters" in dir_name:
            book_name = dir_name.replace("_smart_chapters", "")
        else:
            book_name = dir_name
        
        if book_name not in books:
            books[book_name] = []
        books[book_name].append(dir_path)
    
    # Process each book
    for book_name, dirs in books.items():
        print(f"\n[*] Processing book: {book_name}")
        
        # Find the best directory (manual > generic > smart)
        best_dir = None
        for dir_path in dirs:
            if "manual" in dir_path.name:
                best_dir = dir_path
                break
        
        if not best_dir:
            for dir_path in dirs:
                if "smart" not in dir_path.name:
                    best_dir = dir_path
                    break
        
        if not best_dir:
            best_dir = dirs[0]
        
        print(f"[✓] Best version: {best_dir.name}")
        
        # Count chapters in best directory
        chapter_files = list(best_dir.glob("*.pdf"))
        print(f"[*] Contains {len(chapter_files)} chapter PDFs")
        
        # Remove other directories for this book
        for dir_path in dirs:
            if dir_path != best_dir:
                print(f"[*] Removing duplicate: {dir_path.name}")
                try:
                    shutil.rmtree(dir_path)
                except Exception as e:
                    print(f"[⚠] Could not remove {dir_path}: {e}")
        
        # Rename best directory to clean name
        clean_name = f"{book_name}_chapters"
        if best_dir.name != clean_name:
            new_path = best_dir.parent / clean_name
            if not new_path.exists():
                print(f"[*] Renaming to: {clean_name}")
                try:
                    best_dir.rename(new_path)
                except Exception as e:
                    print(f"[⚠] Could not rename: {e}")

def create_book_summary(base_dir="pdfs/output"):
    """
    Create a summary of all processed books
    """
    base_path = Path(base_dir)
    if not base_path.exists():
        return
    
    print(f"\n[*] Chapter Summary:")
    print("=" * 60)
    
    total_books = 0
    total_chapters = 0
    
    for item in base_path.iterdir():
        if item.is_dir() and "_chapters" in item.name:
            book_name = item.name.replace("_chapters", "")
            chapter_files = list(item.glob("*.pdf"))
            
            if chapter_files:
                total_books += 1
                total_chapters += len(chapter_files)
                
                print(f"\n{book_name}:")
                print(f"  Chapters: {len(chapter_files)}")
                
                # Show first few and last few chapters
                sorted_chapters = sorted(chapter_files, key=lambda x: x.name)
                if len(sorted_chapters) <= 6:
                    for chapter in sorted_chapters:
                        size_kb = chapter.stat().st_size // 1024
                        print(f"    {chapter.name} ({size_kb}KB)")
                else:
                    for chapter in sorted_chapters[:3]:
                        size_kb = chapter.stat().st_size // 1024
                        print(f"    {chapter.name} ({size_kb}KB)")
                    print(f"    ... ({len(sorted_chapters) - 6} more chapters)")
                    for chapter in sorted_chapters[-3:]:
                        size_kb = chapter.stat().st_size // 1024
                        print(f"    {chapter.name} ({size_kb}KB)")
    
    print("=" * 60)
    print(f"Total: {total_books} books, {total_chapters} chapters")

def main():
    if len(sys.argv) > 1:
        base_dir = sys.argv[1]
    else:
        base_dir = "pdfs/output"
    
    print("PDF Chapter Organization Tool")
    print("=" * 40)
    
    organize_chapters(base_dir)
    create_book_summary(base_dir)
    
    print(f"\n[✓] Organization complete")

if __name__ == "__main__":
    main()