#!/usr/bin/env python3
"""
Complete Glyph Decoding Pipeline

This script combines hash-based glyph normalization with TTF character matching:
1. Hash-Based Normalization: Renders glyphs from all batches and groups by perceptual hash
2. TTF Matching: Matches unique glyphs to TTF characters using progressive SSIM

Usage:
    python3 decode_glyphs_complete.py <book_dir> [--fast] [--full] [--progressive]

Options:
    --fast          Early exit on good SSIM matches
    --full          Check all characters in font (not just alphanumeric)
    --progressive   Use multi-stage filtering (32→64→128→256→512→1024px)
"""

import json
import sys
from pathlib import Path
from collections import defaultdict, Counter
import io
from multiprocessing import Pool, cpu_count
import string
import time
import numpy as np

try:
    from PIL import Image, ImageOps
    import imagehash
    import cairosvg
    from svgpathtools import parse_path
    from fontTools.ttLib import TTFont
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.misc.transform import Transform
    from fontTools.pens.transformPen import TransformPen
    from skimage.metrics import structural_similarity as ssim
    from tqdm import tqdm
except ImportError as e:
    print("[!] Missing dependencies! Install with:")
    print("    pip install pillow cairosvg imagehash svgpathtools fonttools scikit-image tqdm")
    sys.exit(1)


# ============================================================================
# PART 1: HASH-BASED GLYPH NORMALIZATION
# ============================================================================

class GlyphHasher:
    """Renders SVG glyphs and computes perceptual hashes"""

    def __init__(self, size=128):
        self.size = size

    def render_glyph(self, glyph_data):
        """Render SVG path as filled shape"""
        path_str = glyph_data.get('path', '')
        if not path_str or path_str.strip() == '':
            return None

        try:
            # Parse path to get bounding box
            path = parse_path(path_str)
            if len(path) == 0:
                return None

            xmin, xmax, ymin, ymax = path.bbox()
            width = xmax - xmin
            height = ymax - ymin

            if width == 0 or height == 0:
                return None

            # Use font metrics for consistent viewbox
            units_per_em = glyph_data.get('unitsPerEm', 1000)
            ascent = glyph_data.get('ascent', 800)
            descent = glyph_data.get('descent', -200)

            # Center glyph both horizontally and vertically
            glyph_center_x = (xmin + xmax) / 2
            glyph_center_y = (ymin + ymax) / 2

            half_width = units_per_em / 2
            font_height = ascent - descent
            half_height = font_height / 2

            viewbox_x = glyph_center_x - half_width
            viewbox_y = glyph_center_y - half_height
            viewbox = f"{viewbox_x} {viewbox_y} {units_per_em} {font_height}"

            # Create SVG document
            svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="{self.size}" height="{self.size}">
  <path d="{path_str}" fill="black"/>
</svg>'''

            # Render using cairosvg
            png_bytes = cairosvg.svg2png(bytestring=svg.encode('utf-8'),
                                         output_width=self.size,
                                         output_height=self.size)

            # Load as RGBA
            img_rgba = Image.open(io.BytesIO(png_bytes))

            # Create white background and composite
            img = Image.new('L', (self.size, self.size), 255)
            if img_rgba.mode == 'RGBA':
                alpha = img_rgba.split()[3]
                inverted = ImageOps.invert(alpha)
                img.paste(0, mask=inverted)

            return img

        except Exception:
            return None

    def compute_hash(self, img):
        """Compute hash - use multiple hash types for better precision"""
        if img is None:
            return None
        # Use average hash (more precise) + dhash (directional) for better uniqueness
        # Larger hash_size = more precision, less chance of collisions
        ahash = str(imagehash.average_hash(img, hash_size=16))
        dhash = str(imagehash.dhash(img, hash_size=16))
        return f"{ahash}_{dhash}"  # Combine both for maximum uniqueness


def process_batch(args):
    """Process a single batch (for multiprocessing)"""
    book_dir, batch_num, save_images = args
    batch_dir = Path(book_dir) / f'batch_{batch_num}'
    glyphs_file = batch_dir / 'glyphs.json'

    if not glyphs_file.exists():
        return None

    hasher = GlyphHasher()
    batch_results = {
        'batch_num': batch_num,
        'glyph_to_hash': {},
        'glyphs_in_text': [],
        'images': {}
    }

    # Load glyphs and compute hashes
    with open(glyphs_file) as f:
        glyph_data = json.load(f)

    for font_data in glyph_data:
        font_family = font_data['fontFamily']
        glyphs = font_data.get('glyphs', {})

        for glyph_id, glyph_info in glyphs.items():
            # Add font metrics
            glyph_info['unitsPerEm'] = font_data.get('unitsPerEm', 1000)
            glyph_info['ascent'] = font_data.get('ascent', 800)
            glyph_info['descent'] = font_data.get('descent', -200)

            # Render and hash
            img = hasher.render_glyph(glyph_info)
            if img is not None:
                phash = hasher.compute_hash(img)
                batch_results['glyph_to_hash'][int(glyph_id)] = {
                    'hash': phash,
                    'font': font_family
                }

                if save_images and phash not in batch_results['images']:
                    batch_results['images'][phash] = img

    # Load text and extract all glyph IDs used
    page_files = sorted(batch_dir.glob('page_data_*.json'))
    for page_file in page_files:
        with open(page_file) as f:
            pages = json.load(f)

        for page in pages:
            for run in page.get('children', []):
                if 'glyphs' in run:
                    batch_results['glyphs_in_text'].extend(run['glyphs'])

    return batch_results


def create_hash_mapping(book_dir):
    """Phase 1: Create hash-based mapping of all glyphs"""
    print(f"\n{'='*80}")
    print(f"PHASE 1: HASH-BASED GLYPH NORMALIZATION")
    print(f"{'='*80}\n")
    print(f"Book directory: {book_dir}")
    print(f"Using all {cpu_count()} CPU cores")

    # Find all batches
    batch_dirs = []
    front_batches = sorted([d for d in book_dir.iterdir() if d.is_dir() and d.name.startswith('batch_front')])
    batch_dirs.extend(front_batches)
    numbered_batches = sorted([d for d in book_dir.iterdir() if d.is_dir() and d.name.startswith('batch_') and not d.name.startswith('batch_front')],
                              key=lambda x: int(x.name.split('_')[1]))
    batch_dirs.extend(numbered_batches)
    batch_nums = list(range(len(batch_dirs)))

    print(f"\n[*] Found {len(batch_dirs)} batches")

    # Process all batches in parallel
    print(f"[*] Processing batches (rendering all glyphs)...")
    with Pool(cpu_count()) as pool:
        batch_args = [(str(book_dir), batch_num, True) for batch_num in batch_nums]
        results = list(pool.imap_unordered(process_batch, batch_args))

    results = [r for r in results if r is not None]
    print(f"[✓] Processed {len(results)} batches")

    # Build hash -> unique_id mapping
    print(f"\n[*] Building hash-based mapping...")
    hash_to_id = {}
    hash_counter = 0
    hash_fonts = {}
    hash_samples = {}
    hash_images = {}

    for result in results:
        batch_num = result['batch_num']

        for phash, img in result.get('images', {}).items():
            if phash not in hash_images:
                hash_images[phash] = img

        for local_glyph_id, glyph_info in result['glyph_to_hash'].items():
            phash = glyph_info['hash']
            font = glyph_info['font']

            if phash not in hash_to_id:
                hash_to_id[phash] = hash_counter
                hash_fonts[hash_counter] = font
                hash_samples[hash_counter] = (batch_num, local_glyph_id)
                hash_counter += 1

    print(f"[✓] Found {len(hash_to_id)} unique glyphs")

    # Verify no hash collisions
    print(f"\n[*] Verifying hash uniqueness...")
    from collections import Counter
    hash_counts = Counter(hash_to_id.keys())
    collisions = {h: count for h, count in hash_counts.items() if count > 1}

    if collisions:
        print(f"⚠ WARNING: Found {len(collisions)} hash collisions!")
        print(f"This means some distinct glyphs are being merged together.")
        print(f"First few collisions:")
        for h, count in list(collisions.items())[:5]:
            print(f"  Hash {h}: {count} glyphs")
        print(f"\n⚠ This will cause incorrect decoding. Please report this issue.")
    else:
        print(f"✓ No hash collisions - each glyph has a unique hash")

    # Normalize all text
    print(f"\n[*] Normalizing all text...")
    all_normalized_glyphs = []

    for result in sorted(results, key=lambda r: r['batch_num']):
        batch_mapping = {}
        for local_glyph_id, glyph_info in result['glyph_to_hash'].items():
            phash = glyph_info['hash']
            batch_mapping[local_glyph_id] = hash_to_id[phash]

        for glyph_id in result['glyphs_in_text']:
            unique_id = batch_mapping.get(glyph_id, -1)
            all_normalized_glyphs.append(unique_id)

    print(f"[✓] Normalized {len(all_normalized_glyphs):,} glyphs")

    # Save results
    output_dir = book_dir / 'hash_mapping'
    output_dir.mkdir(exist_ok=True)

    hash_info = {
        'total_unique_glyphs': len(hash_to_id),
        'hash_to_id': hash_to_id,
        'id_to_font': {str(k): v for k, v in hash_fonts.items()},
        'id_samples': {str(k): {'batch': v[0], 'glyph': v[1]} for k, v in hash_samples.items()}
    }

    with open(output_dir / 'hash_info.json', 'w') as f:
        json.dump(hash_info, f, indent=2)

    with open(output_dir / 'all_glyphs.json', 'w') as f:
        json.dump(all_normalized_glyphs, f)

    # Save glyph images
    images_dir = output_dir / 'glyph_images'
    images_dir.mkdir(exist_ok=True)

    for phash, unique_id in hash_to_id.items():
        if phash in hash_images:
            img = hash_images[phash]
            font = hash_fonts[unique_id]
            img.save(images_dir / f'id_{unique_id:03d}_{font}.png')

    print(f"[✓] Saved to {output_dir}/")

    # Show frequency
    freq = Counter(all_normalized_glyphs)
    print(f"\n[*] Top 20 most frequent glyphs:")
    for unique_id, count in freq.most_common(20):
        pct = count / len(all_normalized_glyphs) * 100
        font = hash_fonts.get(unique_id, 'unknown')
        print(f"    ID {unique_id:3d} ({font:12s}): {count:7,} ({pct:5.2f}%)")

    return output_dir, hash_info


# ============================================================================
# PART 2: TTF CHARACTER MATCHING
# ============================================================================

def render_glyph_by_name(tt, glyph_name, size=128):
    """Render a glyph by name from TTF"""
    glyph_set = tt.getGlyphSet()
    if glyph_name not in glyph_set:
        return None

    glyph = glyph_set[glyph_name]

    # Get font metrics
    head = tt['head']
    units_per_em = head.unitsPerEm
    hhea = tt['hhea']
    ascent = hhea.ascent
    descent = hhea.descent

    # Get bounding box
    bounds_pen = BoundsPen(glyph_set)
    glyph.draw(bounds_pen)
    if bounds_pen.bounds is None:
        return None
    xmin, ymin, xmax, ymax = bounds_pen.bounds

    # Apply Y-flip to bbox
    ymin_svg = -ymax
    ymax_svg = -ymin

    # Extract SVG path with Y-flip
    svg_pen = SVGPathPen(glyph_set)
    transform_pen = TransformPen(svg_pen, Transform(1, 0, 0, -1, 0, 0))
    glyph.draw(transform_pen)
    path_data = svg_pen.getCommands()

    if not path_data or path_data.strip() == '':
        return None

    # Center glyph
    glyph_center_x = (xmin + xmax) / 2
    glyph_center_y = (ymin_svg + ymax_svg) / 2
    font_height = ascent - descent
    viewbox_x = glyph_center_x - units_per_em / 2
    viewbox_y = glyph_center_y - font_height / 2
    viewbox = f"{viewbox_x} {viewbox_y} {units_per_em} {font_height}"

    # Create SVG
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="{size}" height="{size}">
  <path d="{path_data}" fill="black"/>
</svg>'''

    # Render
    try:
        png_bytes = cairosvg.svg2png(
            bytestring=svg.encode('utf-8'),
            output_width=size,
            output_height=size
        )
        img_rgba = Image.open(io.BytesIO(png_bytes))
        img = Image.new('L', (size, size), 255)
        alpha = img_rgba.split()[3]
        inverted = ImageOps.invert(alpha)
        img.paste(0, mask=inverted)
        return img
    except Exception:
        return None


def render_char_from_ttf(tt, char, size=128):
    """Render a character from TTF"""
    cmap = tt.getBestCmap()
    if ord(char) not in cmap:
        return None
    glyph_name = cmap[ord(char)]
    return render_glyph_by_name(tt, glyph_name, size)


def compare_images_ssim(img1, img2):
    """Compare two images using SSIM. Returns distance (0=identical)"""
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    similarity = ssim(arr1, arr2)
    distance = (1 - similarity) * 10
    return distance


def match_single_glyph(args):
    """Match a single glyph (for parallel processing)"""
    unique_id, glyph_images_dir, ttf_library_items, fast_mode, progressive_mode = args

    # Load Amazon glyph image
    glyph_image_files = list(glyph_images_dir.glob(f'id_{unique_id:03d}_*.png'))
    if not glyph_image_files:
        return (unique_id, None, float('inf'))

    amazon_img = Image.open(glyph_image_files[0])

    if not progressive_mode:
        # Original single-pass approach
        best_match = None
        best_distance = float('inf')
        early_exit_threshold = 0.05 if fast_mode else -1

        for (char, font_name, style), ttf_img in ttf_library_items:
            distance = compare_images_ssim(amazon_img, ttf_img)
            if distance < best_distance:
                best_distance = distance
                best_match = (char, font_name, style)

                if fast_mode and distance <= early_exit_threshold:
                    break

        return (unique_id, best_match, best_distance)

    # Progressive resolution approach
    # Stage 1: 128x128 - Quick filter
    amazon_128 = amazon_img.resize((128, 128), Image.LANCZOS)
    candidates_128 = []

    for (char, font_name, style), ttf_img in ttf_library_items:
        ttf_128 = ttf_img.resize((128, 128), Image.LANCZOS)
        distance = compare_images_ssim(amazon_128, ttf_128)
        candidates_128.append(((char, font_name, style), ttf_img, distance))

    # Sort and keep top 30 candidates only
    candidates_128.sort(key=lambda x: x[2])
    candidates_128 = candidates_128[:30]

    # Stage 2: 256x256 - Narrow down
    amazon_256 = amazon_img.resize((256, 256), Image.LANCZOS)
    candidates_256 = []

    for (char, font_name, style), ttf_img, _ in candidates_128:
        ttf_256 = ttf_img.resize((256, 256), Image.LANCZOS)
        distance = compare_images_ssim(amazon_256, ttf_256)
        candidates_256.append(((char, font_name, style), ttf_img, distance))

    # Sort and keep top 10
    candidates_256.sort(key=lambda x: x[2])
    candidates_256 = candidates_256[:10]

    # Stage 3: 512x512 - Final decision
    amazon_512 = amazon_img.resize((512, 512), Image.LANCZOS)
    best_match = None
    best_distance = float('inf')

    for (char, font_name, style), ttf_img, _ in candidates_256:
        ttf_512 = ttf_img.resize((512, 512), Image.LANCZOS)
        distance = compare_images_ssim(amazon_512, ttf_512)
        if distance < best_distance:
            best_distance = distance
            best_match = (char, font_name, style)

            # Early exit if very confident
            if distance < 0.05:
                break

    return (unique_id, best_match, best_distance)


def match_ttf_characters(hash_mapping_dir, fast_mode, full_mode, progressive_mode):
    """Phase 2: Match unique glyphs to TTF characters"""
    print(f"\n{'='*80}")
    print(f"PHASE 2: TTF CHARACTER MATCHING")
    print(f"{'='*80}\n")

    hash_info_file = hash_mapping_dir / 'hash_info.json'
    glyph_images_dir = hash_mapping_dir / 'glyph_images'

    # Load hash info
    with open(hash_info_file) as f:
        hash_info = json.load(f)

    id_to_font = {int(k): v for k, v in hash_info['id_to_font'].items()}

    # Find all font files (check multiple directories)
    font_dirs = [Path('fonts'), Path('.')]
    font_files = []
    for font_dir in font_dirs:
        if font_dir.exists():
            font_files.extend(font_dir.glob('*.ttf'))

    font_files = sorted(set(font_files))  # Remove duplicates
    print(f"Found {len(font_files)} font files")

    # Check which fonts we have vs what the book needs
    found_font_names = {f.stem.lower() for f in font_files}
    needed_fonts = set(id_to_font.values())
    missing_fonts = needed_fonts - found_font_names

    if missing_fonts:
        print(f"\n⚠ WARNING: Book uses fonts not in font directory:")
        for font in missing_fonts:
            glyph_count = sum(1 for f in id_to_font.values() if f == font)
            print(f"  - {font}: {glyph_count} glyphs")
        print(f"\nGlyphs using these fonts will be matched against available fonts (may be inaccurate)")
    else:
        print(f"✓ All required fonts available")

    # Characters to test
    if full_mode:
        chars_to_test = []
        print("Full mode: Will check ALL characters in font")
    else:
        # Standard ASCII characters
        chars_to_test = string.ascii_letters + string.digits + string.punctuation + " "

        # Add common special characters that appear in books
        special_chars = [
            '\u2022',  # • BULLET
            '\u2023',  # ‣ TRIANGULAR BULLET
            '\u2043',  # ⁃ HYPHEN BULLET
            '\u00B7',  # · MIDDLE DOT
            '\u25E6',  # ◦ WHITE BULLET
            '\u2219',  # ∙ BULLET OPERATOR
            '\u00A0',  # Non-breaking space
            '\u00A9',  # © COPYRIGHT
            '\u00AE',  # ® REGISTERED
            '\u2122',  # ™ TRADEMARK
            '\u00AB',  # « LEFT DOUBLE ANGLE QUOTE
            '\u00BB',  # » RIGHT DOUBLE ANGLE QUOTE
            '\u2018',  # ' LEFT SINGLE QUOTE (already in ligatures but add anyway)
            '\u2019',  # ' RIGHT SINGLE QUOTE
            '\u201A',  # ‚ SINGLE LOW-9 QUOTE
            '\u201B',  # ‛ SINGLE HIGH-REVERSED-9 QUOTE
            '\u2032',  # ′ PRIME
            '\u2033',  # ″ DOUBLE PRIME
        ]
        chars_to_test += ''.join(special_chars)
        print(f"Standard mode: Checking {len(chars_to_test)} predefined characters (including special chars)")

    # Ligatures and special glyphs
    ligature_glyphs = {
        'f_f': 'ff', 'f_i': 'fi', 'f_l': 'fl', 'f_f_i': 'ffi', 'f_f_l': 'ffl',
        'uniFB00': 'ff', 'uniFB01': 'fi', 'uniFB02': 'fl', 'uniFB03': 'ffi', 'uniFB04': 'ffl',
        'space': ' ',
        'endash': chr(0x2013), 'emdash': chr(0x2014),
        'quotedblleft': chr(0x201C), 'quotedblright': chr(0x201D),
        'quoteleft': chr(0x2018), 'quoteright': chr(0x2019),
        'ellipsis': chr(0x2026),
    }

    # Build TTF character library
    print("=" * 60)
    print("Building TTF character library...")
    print("=" * 60)

    ttf_library = {}

    for font_path in font_files:
        font_name = font_path.stem
        print(f"\nProcessing: {font_name}")

        font_style = "normal"
        if "Bold" in font_name and "Italic" in font_name:
            font_style = "bold-italic"
        elif "Bold" in font_name:
            font_style = "bold"
        elif "Italic" in font_name:
            font_style = "italic"

        try:
            tt = TTFont(font_path)
            rendered_count = 0

            if full_mode:
                cmap = tt.getBestCmap()
                if cmap:
                    for codepoint, glyph_name in cmap.items():
                        char = chr(codepoint)
                        img = render_char_from_ttf(tt, char)
                        if img is not None:
                            ttf_library[(char, font_name, font_style)] = img
                            rendered_count += 1
            else:
                for char in chars_to_test:
                    img = render_char_from_ttf(tt, char)
                    if img is not None:
                        ttf_library[(char, font_name, font_style)] = img
                        rendered_count += 1

            # Render ligatures and special characters
            glyph_set = tt.getGlyphSet()
            for glyph_name, char in ligature_glyphs.items():
                if glyph_name in glyph_set:
                    img = render_glyph_by_name(tt, glyph_name)
                    if img is not None:
                        ttf_library[(char, font_name, font_style)] = img
                        rendered_count += 1

            print(f"  Rendered {rendered_count} glyphs")

        except Exception as e:
            print(f"  Error: {e}")

    print(f"\n[✓] TTF library built: {len(ttf_library)} glyphs")

    # Match glyphs
    print("\n" + "=" * 60)
    mode_parts = []
    if progressive_mode:
        mode_parts.append("PROGRESSIVE MODE - 3-stage filtering (128→256→512px)")
    elif fast_mode:
        mode_parts.append("FAST MODE - early exit on good matches")
    else:
        mode_parts.append("FULL MODE - exhaustive search")

    print(f"Matching Amazon glyphs to TTF characters (using SSIM, {cpu_count()} threads)")
    print(f"{' | '.join(mode_parts)}")
    print("=" * 60)

    # Prepare arguments
    ttf_library_items = list(ttf_library.items())
    glyph_ids = sorted(id_to_font.keys())
    args_list = [(gid, glyph_images_dir, ttf_library_items, fast_mode, progressive_mode) for gid in glyph_ids]

    # Process in parallel
    matches = {}
    no_match_count = 0

    start_time = time.time()
    with Pool(cpu_count()) as pool:
        results = list(tqdm(pool.imap(match_single_glyph, args_list), total=len(args_list), desc="Matching glyphs"))
    elapsed_time = time.time() - start_time

    for unique_id, best_match, best_distance in results:
        if best_match and best_distance <= 1.0:
            matches[unique_id] = (*best_match, best_distance)
            # Highlight potential mismatches
            if best_match[0] in [',', "'", '"', '`'] and best_distance > 0.3:
                print(f"⚠ Glyph {unique_id:3d} → '{best_match[0]}' (distance={best_distance:.3f}, font={best_match[1]}) [UNCERTAIN]")
            else:
                print(f"✓ Glyph {unique_id:3d} → '{best_match[0]}' (distance={best_distance:.3f}, font={best_match[1]})")
        else:
            no_match_count += 1
            print(f"✗ Glyph {unique_id:3d} → NO MATCH (best distance={best_distance:.3f})")

    # Add special case for space
    matches[-1] = (' ', 'special', 'normal', 0)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Matched: {len(matches)-1}/{len(id_to_font)} glyphs ({100*(len(matches)-1)/len(id_to_font):.0f}%)")
    print(f"No match: {no_match_count} glyphs")
    print(f"Time taken: {elapsed_time:.2f} seconds")
    print(f"\nUnmatched glyph IDs: {[k for k in sorted(id_to_font.keys()) if k not in matches]}")

    # Save mapping
    output_file = Path('ttf_character_mapping.json')
    mapping_output = {
        str(glyph_id): {
            "character": char,
            "font": font,
            "style": style,
            "distance": dist
        }
        for glyph_id, (char, font, style, dist) in matches.items()
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(mapping_output, f, indent=2, ensure_ascii=False)

    print(f"\nMapping saved to: {output_file}")

    # Show character frequency
    char_counts = defaultdict(int)
    style_counts = defaultdict(int)
    for char, _font, style, _dist in matches.values():
        char_counts[char] += 1
        style_counts[style] += 1

    print("\nMost common matched characters:")
    for char, count in sorted(char_counts.items(), key=lambda x: -x[1])[:20]:
        print(f"  '{char}': {count} glyphs")

    print("\nMatches by style:")
    for style, count in sorted(style_counts.items()):
        print(f"  {style}: {count} glyphs")

    return output_file


# ============================================================================
# MAIN
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 decode_glyphs_complete.py <book_dir> [--fast] [--full] [--progressive]")
        print("\nOptions:")
        print("  --fast          Early exit on good SSIM matches")
        print("  --full          Check all characters in font (not just alphanumeric)")
        print("  --progressive   Use multi-stage filtering (32→64→128→256→512→1024px)")
        sys.exit(1)

    fast_mode = "--fast" in sys.argv
    full_mode = "--full" in sys.argv
    progressive_mode = "--progressive" in sys.argv
    book_dir = Path(sys.argv[1])

    print(f"\n{'='*80}")
    print(f"COMPLETE GLYPH DECODING PIPELINE")
    print(f"{'='*80}")
    print(f"\nBook: {book_dir}")
    print(f"Options:")
    print(f"  Fast mode: {fast_mode}")
    print(f"  Full character set: {full_mode}")
    print(f"  Progressive matching: {progressive_mode}")

    # Phase 1: Hash-based normalization
    hash_mapping_dir, hash_info = create_hash_mapping(book_dir)

    # Phase 2: TTF character matching
    mapping_file = match_ttf_characters(hash_mapping_dir, fast_mode, full_mode, progressive_mode)

    print(f"\n{'='*80}")
    print(f"[✓] COMPLETE PIPELINE FINISHED!")
    print(f"{'='*80}")
    print(f"\nOutputs:")
    print(f"  Hash mapping: {hash_mapping_dir}/")
    print(f"  Character mapping: {mapping_file}")


if __name__ == '__main__':
    main()
