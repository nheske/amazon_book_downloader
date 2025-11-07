# PDF Chapter Splitting Tools

This collection of tools allows you to split PDF books into individual chapter PDFs with high quality and proper chapter boundaries.

## Tools Overview

### 1. `generic_chapter_split.py` - Main Tool (Recommended)
The primary tool for splitting PDFs into chapters. Supports both automatic detection for known books and manual chapter definitions.

**Usage:**
```bash
# Auto-detect known books (like Modern Poker Theory)
python generic_chapter_split.py "book.pdf"

# Use custom chapter definitions
python generic_chapter_split.py "book.pdf" --chapters my_chapters.json

# Create a template for defining chapters
python generic_chapter_split.py --template my_chapters.json
```

**Known Books:**
- Modern Poker Theory by Michael Acevedo (auto-detected)

### 2. `manual_chapter_split.py` - Manual Definitions
Specifically designed for Modern Poker Theory with hard-coded chapter structure. Provides the highest quality results.

**Usage:**
```bash
python manual_chapter_split.py "pdfs/Modern Poker Theory_Acevedo.pdf" "output_dir"
```

### 3. `smart_chapter_split.py` - Automatic Detection
Attempts to automatically detect chapters using multiple analysis methods. Results may vary in quality.

**Usage:**
```bash
python smart_chapter_split.py "book.pdf" "output_dir"
```

### 4. `organize_chapters.py` - Output Management
Organizes and cleans up chapter output directories, removing duplicates and providing summaries.

**Usage:**
```bash
python organize_chapters.py [output_directory]
```

## For New Books

### Method 1: Create Chapter Definition File

1. **Create a template:**
   ```bash
   python generic_chapter_split.py --template my_book_chapters.json
   ```

2. **Edit the JSON file** with your book's actual chapter structure:
   ```json
   [
     {
       "number": 1,
       "title": "Introduction",
       "start_page": 15
     },
     {
       "number": 2,
       "title": "Getting Started", 
       "start_page": 28
     }
   ]
   ```
   
   **Important Notes:**
   - Page numbers are 0-based (first page of PDF = 0)
   - You can find page numbers by opening the PDF and noting where chapters start
   - The tool automatically calculates end pages (start of next chapter - 1)

3. **Split the chapters:**
   ```bash
   python generic_chapter_split.py "my_book.pdf" --chapters my_book_chapters.json
   ```

### Method 2: Add to Known Books

Edit `generic_chapter_split.py` and add your book to the `KNOWN_BOOKS` dictionary:

```python
KNOWN_BOOKS = {
    "my_book": {
        "patterns": ["my book title", "author name"],
        "chapters": [
            {'number': 1, 'title': 'Chapter 1', 'start_page': 10},
            {'number': 2, 'title': 'Chapter 2', 'start_page': 25},
            # ... more chapters
        ]
    }
}
```

## Output Structure

```
pdfs/output/
├── BookName_chapters/
│   ├── chapter_01_Title.pdf
│   ├── chapter_02_Title.pdf
│   └── ...
```

## Quality Results

**Manual/Generic Tool Results:**
- ✅ Proper chapter boundaries
- ✅ Complete chapters with full content
- ✅ Reasonable chapter lengths (10-150 pages typical)
- ✅ Clean, descriptive filenames

**Automatic Detection Issues:**
- ❌ May detect text fragments instead of chapters
- ❌ Can miss actual chapter starts
- ❌ May create chapters with nonsensical titles
- ❌ Inconsistent page counts

## Example: Modern Poker Theory Results

**High Quality (Manual/Generic):**
```
chapter_01_Poker Fundamentals.pdf (66 pages)
chapter_02_The Elements of Game Theory.pdf (64 pages)  
chapter_03_Modern Poker Software.pdf (2 pages)
chapter_04_The Theory of Pre-flop Play.pdf (30 pages)
...
```

**Low Quality (Automatic):**
```
chapter_84_and stack depth.pdf (? pages)  # Fragment detection
chapter_03_♦ The only set the BB has is 33.pdf  # Mid-sentence start
```

## Tips for Best Results

1. **Use Manual Definitions:** For important books, take time to manually identify chapter start pages
2. **Check Page Numbers:** Use a PDF viewer to find exact page numbers where chapters begin
3. **Validate Results:** Check a few generated chapters to ensure they contain complete content
4. **Use Zero-Based Pages:** Remember that PDF page numbering starts at 0, not 1
5. **Clean Up:** Use `organize_chapters.py` to remove duplicate/poor quality results

## Dependencies

- `PyPDF2` - For PDF manipulation
- `pathlib` - For path handling (built-in)
- `json` - For chapter definitions (built-in)

Install with:
```bash
pip install PyPDF2
```

## Integration with EPUB Tools

These PDF tools work alongside the EPUB processing tools in this project:
- `split_epub_chapters.py` - For splitting EPUB files
- `convert_epub_to_pdf.py` - For converting EPUB to PDF
- `create_epub.py` - For creating EPUB from Kindle downloads

You can process books downloaded from Kindle Cloud Reader through the full pipeline:
1. Download → `download_full_book.py`
2. Decode → `decode_glyphs_complete.py` 
3. Create EPUB → `create_epub.py`
4. Convert to PDF → `convert_epub_to_pdf.py`
5. Split chapters → `generic_chapter_split.py`