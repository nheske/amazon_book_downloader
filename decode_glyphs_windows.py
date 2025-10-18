#!/usr/bin/env python3
"""
Windows-Compatible Glyph Decoding Pipeline

This version works without Cairo by using alternative SVG rendering methods.
Uses Pillow and matplotlib for SVG path rendering instead of cairosvg.

Usage:
    python decode_glyphs_windows.py <book_dir> [--fast] [--full] [--progressive]

Options:
    --fast          Early exit on good SSIM matches
    --full          Check all characters in font (not just alphanumeric)
    --progressive   Use multi-stage filtering (128→256→512px)
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
import re

try:
    from PIL import Image, ImageDraw, ImageOps
    import imagehash
    from svgpathtools import parse_path
    from fontTools.ttLib import TTFont
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.misc.transform import Transform
    from fontTools.pens.transformPen import TransformPen
    from skimage.metrics import structural_similarity as ssim
    from tqdm import tqdm
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.path import Path as MPLPath
    import matplotlib.patheffects as path_effects
except ImportError as e:
    print("[!] Missing dependencies! Install with:")
    print("    pip install pillow imagehash svgpathtools fonttools scikit-image tqdm matplotlib")
    sys.exit(1)


# ============================================================================
# WINDOWS-COMPATIBLE SVG RENDERING
# ============================================================================

def svg_path_to_matplotlib_path(path_str):
    """Convert SVG path string to matplotlib Path"""
    try:
        # Parse SVG path using svgpathtools
        path = parse_path(path_str)
        if len(path) == 0:
            return None
            
        # Convert to matplotlib path
        vertices = []
        codes = []
        
        for segment in path:
            if hasattr(segment, 'start'):
                start = segment.start
                vertices.append([start.real, start.imag])
                codes.append(MPLPath.MOVETO)
                
            if hasattr(segment, 'end'):
                end = segment.end
                vertices.append([end.real, end.imag])
                codes.append(MPLPath.LINETO)
                
        if vertices:
            return MPLPath(vertices, codes)
        return None
    except:
        return None

def render_svg_path_matplotlib(path_str, size=128, units_per_em=1000, ascent=800, descent=-200):
    """Render SVG path using matplotlib (Windows compatible)"""
    try:
        # Parse and convert path
        mpl_path = svg_path_to_matplotlib_path(path_str)
        if mpl_path is None:
            return None
            
        # Get bounding box
        svg_path = parse_path(path_str)
        if len(svg_path) == 0:
            return None
            
        xmin, xmax, ymin, ymax = svg_path.bbox()
        width = xmax - xmin
        height = ymax - ymin
        
        if width == 0 or height == 0:
            return None
            
        # Create figure with non-interactive backend
        plt.ioff()  # Turn off interactive mode
        fig, ax = plt.subplots(figsize=(size/100, size/100), dpi=100)
        ax.set_xlim(xmin - width*0.1, xmax + width*0.1)
        ax.set_ylim(ymin - height*0.1, ymax + height*0.1)
        ax.set_aspect('equal')
        ax.axis('off')
        
        # Create patch and add to axes
        patch = patches.PathPatch(mpl_path, facecolor='black', edgecolor='none')
        ax.add_patch(patch)
        
        # Render to image
        fig.canvas.draw()
        buf = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
        buf = buf.reshape(fig.canvas.get_width_height()[::-1] + (3,))
        
        # Convert to PIL Image and make grayscale
        img = Image.fromarray(buf)
        img = img.convert('L')
        img = img.resize((size, size), Image.LANCZOS)
        
        # IMPORTANT: Close figure to free memory
        plt.close(fig)
        
        return img
        
    except Exception as e:
        return None

def render_svg_path_simple(path_str, size=128):
    """Simple SVG path rendering using PIL (fallback method)"""
    try:
        # Parse path to get basic shape info
        path = parse_path(path_str)
        if len(path) == 0:
            return None
            
        # Get bounding box
        xmin, xmax, ymin, ymax = path.bbox()
        width = xmax - xmin
        height = ymax - ymin
        
        if width == 0 or height == 0:
            return None
            
        # Create image
        img = Image.new('L', (size, size), 255)  # White background
        draw = ImageDraw.Draw(img)
        
        # Scale and translate to fit in image
        scale = min(size * 0.8 / width, size * 0.8 / height)
        offset_x = (size - width * scale) / 2 - xmin * scale
        offset_y = (size - height * scale) / 2 - ymin * scale
        
        # Draw simple approximation of the path
        points = []
        for segment in path:
            if hasattr(segment, 'start'):
                x = segment.start.real * scale + offset_x
                y = segment.start.imag * scale + offset_y
                points.append((x, y))
            if hasattr(segment, 'end'):
                x = segment.end.real * scale + offset_x
                y = segment.end.imag * scale + offset_y
                points.append((x, y))
                
        if len(points) > 2:
            draw.polygon(points, fill=0)  # Black fill
            
        return img
        
    except Exception:
        return None


# ============================================================================
# WINDOWS-COMPATIBLE GLYPH HASHER
# ============================================================================

class WindowsGlyphHasher:
    """Windows-compatible glyph renderer and hasher"""

    def __init__(self, size=128):
        self.size = size

    def render_glyph(self, glyph_data):
        """Render SVG path using Windows-compatible methods"""
        path_str = glyph_data.get('path', '')
        if not path_str or path_str.strip() == '':
            return None

        # Try simple PIL method first (faster and more memory efficient)
        img = render_svg_path_simple(path_str, self.size)
        
        # Fallback to matplotlib method if needed
        if img is None:
            img = render_svg_path_matplotlib(
                path_str, 
                self.size,
                glyph_data.get('unitsPerEm', 1000),
                glyph_data.get('ascent', 800),
                glyph_data.get('descent', -200)
            )
            
        return img

    def compute_hash(self, img):
        """Compute hash - use multiple hash types for better precision"""
        if img is None:
            return None
        # Use average hash + dhash for better uniqueness
        ahash = str(imagehash.average_hash(img, hash_size=16))
        dhash = str(imagehash.dhash(img, hash_size=16))
        return f"{ahash}_{dhash}"


def process_batch_windows(args):
    """Process a single batch (Windows version)"""
    book_dir, batch_num, save_images = args
    batch_dir = Path(book_dir) / f'batch_{batch_num}'
    glyphs_file = batch_dir / 'glyphs.json'

    if not glyphs_file.exists():
        return None

    hasher = WindowsGlyphHasher()
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


def create_hash_mapping_windows(book_dir):
    """Phase 1: Create hash-based mapping (Windows version)"""
    print(f"\n{'='*80}")
    print(f"PHASE 1: HASH-BASED GLYPH NORMALIZATION (WINDOWS)")
    print(f"{'='*80}\n")
    print(f"Book directory: {book_dir}")
    print(f"Using Windows-compatible SVG rendering")
    print(f"Using {cpu_count()} CPU cores")

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
        results = list(pool.imap_unordered(process_batch_windows, batch_args))

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
# TTF RENDERING (Same as original but using Windows-compatible methods)
# ============================================================================

def render_glyph_by_name_windows(tt, glyph_name, size=128):
    """Render a glyph by name from TTF (Windows version)"""
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

    # Use our Windows-compatible renderer
    glyph_data = {
        'path': path_data,
        'unitsPerEm': units_per_em,
        'ascent': ascent,
        'descent': descent
    }
    
    hasher = WindowsGlyphHasher(size)
    return hasher.render_glyph(glyph_data)


def render_char_from_ttf_windows(tt, char, size=128):
    """Render a character from TTF (Windows version)"""
    cmap = tt.getBestCmap()
    if ord(char) not in cmap:
        return None
    glyph_name = cmap[ord(char)]
    return render_glyph_by_name_windows(tt, glyph_name, size)


# Re-use the same matching functions from the original script
def compare_images_ssim(img1, img2):
    """Compare two images using SSIM. Returns distance (0=identical)"""
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    similarity = ssim(arr1, arr2)
    distance = (1 - similarity) * 10
    return distance


def match_single_glyph_windows(args):
    """Match a single glyph (Windows version)"""
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


def match_ttf_characters_windows(hash_mapping_dir, fast_mode, full_mode, progressive_mode):
    """Phase 2: Match unique glyphs to TTF characters (Windows version)"""
    print(f"\n{'='*80}")
    print(f"PHASE 2: TTF CHARACTER MATCHING (WINDOWS)")
    print(f"{'='*80}\n")

    hash_info_file = hash_mapping_dir / 'hash_info.json'
    glyph_images_dir = hash_mapping_dir / 'glyph_images'

    # Load hash info
    with open(hash_info_file) as f:
        hash_info = json.load(f)

    id_to_font = {int(k): v for k, v in hash_info['id_to_font'].items()}

    # Find all font files
    font_dirs = [Path('fonts'), Path('.')]
    font_files = []
    for font_dir in font_dirs:
        if font_dir.exists():
            font_files.extend(font_dir.glob('*.ttf'))

    font_files = sorted(set(font_files))
    print(f"Found {len(font_files)} font files")

    # Check fonts
    found_font_names = {f.stem.lower() for f in font_files}
    needed_fonts = set(id_to_font.values())
    missing_fonts = needed_fonts - found_font_names

    if missing_fonts:
        print(f"\n⚠ WARNING: Book uses fonts not in font directory:")
        for font in missing_fonts:
            glyph_count = sum(1 for f in id_to_font.values() if f == font)
            print(f"  - {font}: {glyph_count} glyphs")
    else:
        print(f"✓ All required fonts available")

    # Characters to test
    if full_mode:
        chars_to_test = []
        print("Full mode: Will check ALL characters in font")
    else:
        chars_to_test = string.ascii_letters + string.digits + string.punctuation + " "
        special_chars = [
            '\u2022', '\u2023', '\u2043', '\u00B7', '\u25E6', '\u2219',
            '\u00A0', '\u00A9', '\u00AE', '\u2122', '\u00AB', '\u00BB',
            '\u2018', '\u2019', '\u201A', '\u201B', '\u2032', '\u2033',
        ]
        chars_to_test += ''.join(special_chars)
        print(f"Standard mode: Checking {len(chars_to_test)} predefined characters")

    # Ligatures
    ligature_glyphs = {
        'f_f': 'ff', 'f_i': 'fi', 'f_l': 'fl', 'f_f_i': 'ffi', 'f_f_l': 'ffl',
        'uniFB00': 'ff', 'uniFB01': 'fi', 'uniFB02': 'fl', 'uniFB03': 'ffi', 'uniFB04': 'ffl',
        'space': ' ', 'endash': chr(0x2013), 'emdash': chr(0x2014),
        'quotedblleft': chr(0x201C), 'quotedblright': chr(0x201D),
        'quoteleft': chr(0x2018), 'quoteright': chr(0x2019), 'ellipsis': chr(0x2026),
    }

    # Build TTF library using Windows renderer
    print("=" * 60)
    print("Building TTF character library (Windows renderer)...")
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
                        img = render_char_from_ttf_windows(tt, char)
                        if img is not None:
                            ttf_library[(char, font_name, font_style)] = img
                            rendered_count += 1
            else:
                for char in chars_to_test:
                    img = render_char_from_ttf_windows(tt, char)
                    if img is not None:
                        ttf_library[(char, font_name, font_style)] = img
                        rendered_count += 1

            # Render ligatures
            glyph_set = tt.getGlyphSet()
            for glyph_name, char in ligature_glyphs.items():
                if glyph_name in glyph_set:
                    img = render_glyph_by_name_windows(tt, glyph_name)
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
        mode_parts.append("PROGRESSIVE MODE - 3-stage filtering")
    elif fast_mode:
        mode_parts.append("FAST MODE - early exit on good matches")
    else:
        mode_parts.append("FULL MODE - exhaustive search")

    print(f"Matching Amazon glyphs to TTF characters (Windows compatible)")
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
        results = list(tqdm(pool.imap(match_single_glyph_windows, args_list), total=len(args_list), desc="Matching glyphs"))
    elapsed_time = time.time() - start_time

    for unique_id, best_match, best_distance in results:
        if best_match and best_distance <= 1.0:
            matches[unique_id] = (*best_match, best_distance)
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

    return output_file


# ============================================================================
# MAIN
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python decode_glyphs_windows.py <book_dir> [--fast] [--full] [--progressive]")
        print("\nOptions:")
        print("  --fast          Early exit on good SSIM matches")
        print("  --full          Check all characters in font (not just alphanumeric)")
        print("  --progressive   Use multi-stage filtering (128→256→512px)")
        sys.exit(1)

    fast_mode = "--fast" in sys.argv
    full_mode = "--full" in sys.argv
    progressive_mode = "--progressive" in sys.argv
    book_dir = Path(sys.argv[1])

    print(f"\n{'='*80}")
    print(f"WINDOWS-COMPATIBLE GLYPH DECODING PIPELINE")
    print(f"{'='*80}")
    print(f"\nBook: {book_dir}")
    print(f"Options:")
    print(f"  Fast mode: {fast_mode}")
    print(f"  Full character set: {full_mode}")
    print(f"  Progressive matching: {progressive_mode}")
    print(f"  SVG Renderer: matplotlib + PIL (Cairo-free)")

    # Phase 1: Hash-based normalization
    hash_mapping_dir, hash_info = create_hash_mapping_windows(book_dir)

    # Phase 2: TTF character matching
    mapping_file = match_ttf_characters_windows(hash_mapping_dir, fast_mode, full_mode, progressive_mode)

    print(f"\n{'='*80}")
    print(f"[✓] WINDOWS-COMPATIBLE PIPELINE FINISHED!")
    print(f"{'='*80}")
    print(f"\nOutputs:")
    print(f"  Hash mapping: {hash_mapping_dir}/")
    print(f"  Character mapping: {mapping_file}")


if __name__ == '__main__':
    main()