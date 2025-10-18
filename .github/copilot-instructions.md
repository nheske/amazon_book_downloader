# Amazon Kindle Book Downloader - AI Coding Assistant Instructions

## Project Overview
This is a sophisticated reverse-engineering tool that downloads and reconstructs Amazon Kindle books from Kindle Cloud Reader into readable EPUB files. The process involves web scraping encrypted content, glyph-level OCR decoding, and EPUB reconstruction.

## Core Architecture (3-Stage Pipeline)

### Stage 1: Raw Download (`downloader.py`, `download_full_book.py`)
- **Session Management**: Single persistent session across entire book download to maintain consistent font/glyph encoding
- **Authentication**: Uses `headers.json` with encrypted cookies and optional `x-adp-session-token`
- **Batch Strategy**: Downloads 5 pages at a time starting from position 0 (includes TOC/front matter)
- **API Endpoints**: 
  - `startReading` → Gets `karamelToken` and book metadata
  - `render` → Returns TAR archives with SVG glyphs, page data, TOC
- **Output Structure**: `downloads/{ASIN}/batch_{N}/` containing `glyphs.json`, `page_data_*.json`, `toc.json`

### Stage 2: Glyph Decoding (`decode_glyphs_complete.py`)
- **Hash Normalization**: Renders SVG paths → PNG images → perceptual hashes to deduplicate glyphs across batches
- **TTF Matching**: Compares Amazon glyphs to local Bookerly TTF fonts using SSIM (Structural Similarity)
- **Progressive Matching**: Multi-resolution approach (128→256→512px) for accuracy vs speed
- **Output**: `ttf_character_mapping.json` mapping glyph IDs to Unicode characters

### Stage 3: EPUB Creation (`create_epub.py`)
- **Text Reconstruction**: Uses character mapping to convert glyph sequences to readable text
- **Layout Analysis**: Detects alignment, indentation, line breaks from glyph positioning data
- **Chapter Structure**: Maps TOC position IDs to glyph indices for proper chapter boundaries
- **Typography**: Preserves font styles (italic, bold), sizes, and Kindle-specific formatting

## Critical Implementation Patterns

### Single-Session Requirement
The entire book MUST be downloaded in one session (`KindleDownloader` instance) because:
- Font encoding changes between sessions
- Glyph IDs are session-specific
- TOC from first batch provides the reference mapping

### Glyph ID Handling
- Local glyph IDs (per-batch) → Hash-based unique IDs → Character mapping
- Use `all_glyphs.json` as the canonical text sequence
- Handle missing/unmapped glyphs with fallback notation `[{glyph_id}]`

### Font File Organization
- `/fonts/` directory contains complete Bookerly font family (12 variants)
- Font matching requires exact style detection (`Bold`, `Italic`, `Display`, `LCD`)
- Critical for accurate character reconstruction

### Error Handling Conventions
- Prefix output with status indicators: `[✓]` success, `[✗]` error, `[⚠]` warning, `[*]` info
- Always validate `headers.json` structure before network requests
- Graceful degradation: continue processing even with some failed matches

## Configuration Requirements

### Authentication Setup
```json
// headers.json - REQUIRED for all operations
{
  "headers": {"x-adp-session-token": "optional"},
  "cookies": "session-id=...; other-cookie=..." // Encrypted format supported
}
```

### Processing Parameters
- Default download: 5 pages/batch from position 0
- Font rendering: 128px base size, Bookerly family, 8.91pt size
- SSIM threshold: <1.0 for matches, <0.05 for high confidence

## Development Workflow

### Testing Changes
1. Test with small downloads first: `python downloader.py {ASIN} --pages 2`
2. Verify glyph extraction: check `batch_0/glyphs.json` structure
3. Test character mapping: ensure TTF fonts are in `/fonts/` directory
4. Validate EPUB: verify chapter boundaries and text accuracy

### Performance Optimization
- Use multiprocessing for glyph hashing/matching (defaults to all CPU cores)
- Enable `--fast` mode for quicker SSIM matching during development
- `--progressive` mode provides better accuracy for production

### Font Management
- Keep complete Bookerly font collection in `/fonts/`
- Missing fonts trigger warnings but processing continues
- Font style detection is case-sensitive (`Bold` not `bold`)

## Common Debugging Scenarios
- **Empty pages**: Check cookie expiration in `headers.json`
- **Garbled text**: Verify single-session download and font availability  
- **Missing chapters**: Ensure TOC position mapping is correct
- **Performance issues**: Use `--fast` or reduce batch size for testing