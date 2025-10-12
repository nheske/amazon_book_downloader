#!/usr/bin/env python3
"""
Download complete book by downloading 5 pages at a time in a single session.
This ensures all pages share the same font/glyph encoding.

Strategy:
1. Download from start position (includes TOC) - 5 pages at a time
2. Keep downloading until we reach the end
3. All downloads in ONE session so fonts match
4. Use TOC from first download to build glyph mapping
5. Decode all pages using that single mapping
"""
import json
import sys
from pathlib import Path
from downloader import KindleDownloader

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 download_full_book.py <ASIN> [--yes]")
        sys.exit(1)

    asin = sys.argv[1]
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv
    output_base = Path(f'downloads/{asin}')
    output_base.mkdir(parents=True, exist_ok=True)

    # Load credentials
    headers_file = Path('headers.json')
    if not headers_file.exists():
        print("[✗] headers.json not found!")
        sys.exit(1)

    with open(headers_file) as f:
        headers_data = json.load(f)

    cookies = headers_data.get('cookies', '')
    adp_token = headers_data['headers'].get('x-adp-session-token') if 'headers' in headers_data else None

    # Initialize downloader (single session for entire book)
    print(f"\n{'='*80}")
    print(f"DOWNLOADING COMPLETE BOOK: {asin}")
    print(f"{'='*80}\n")

    downloader = KindleDownloader(cookies, adp_token)

    # Get book metadata
    print("[*] Getting book metadata...")
    metadata = downloader.start_reading(asin)

    title = metadata.get('deliveredAsin', asin)
    revision = metadata.get('contentVersion', '')
    start_pos = metadata.get('srl', 0)

    print(f"[*] Title: {title}")
    print(f"[*] Revision: {revision}")
    print(f"[*] Default start position (srl): {start_pos}")
    print(f"[*] Downloading from position 0 to include front matter (TOC, cover, etc)")

    # Save karamelToken for image decryption
    if 'karamelToken' in metadata:
        karamel_token = {
            'token': metadata['karamelToken']['token'],
            'expiresAt': metadata['karamelToken']['expiresAt']
        }
        token_file = output_base / 'karamel_token.json'
        with open(token_file, 'w') as f:
            json.dump(karamel_token, f, indent=2)
        print(f"[✓] Saved karamelToken to {token_file}")

    # Download from position 0 to get the complete book including front matter
    print(f"\n[*] Batch 0: position 0...")
    first_tar = downloader.render_pages(asin, revision, start_position=0, num_pages=5)
    first_files = downloader.extract_tar(first_tar, output_base / 'batch_0')

    # Get position range from batch 0
    page_data_file = list((output_base / 'batch_0').glob('page_data_*.json'))[0]
    with open(page_data_file) as f:
        first_pages = json.load(f)

    batch_0_start = first_pages[0]['startPositionId']
    batch_0_end = first_pages[-1]['endPositionId']
    print(f"[✓] Batch 0: {batch_0_start} to {batch_0_end} ({len(first_files)} files)")

    # Load TOC to estimate book length
    toc_file = output_base / 'batch_0' / 'toc.json'
    with open(toc_file) as f:
        toc = json.load(f)

    last_toc_pos = max(entry['tocPositionId'] for entry in toc)
    print(f"[*] Book ends around position {last_toc_pos}")

    # Estimate number of batches
    positions_per_batch = batch_0_end - batch_0_start
    estimated_batches = int((last_toc_pos - start_pos) / positions_per_batch) + 1

    print(f"[*] Estimated {estimated_batches} batches needed (~{positions_per_batch} positions per 5 pages)")
    print(f"\n[!] WARNING: This will download the entire book!")
    print(f"[!] Estimated total: {estimated_batches * 5} pages")

    if not auto_confirm:
        response = input(f"\nContinue? [y/N]: ")
        if response.lower() != 'y':
            print("[*] Aborted")
            sys.exit(0)
    else:
        print("[*] Auto-confirmed with --yes flag")

    # Download remaining batches starting from where batch_0 ended
    current_pos = batch_0_end + 1
    batch_num = 1

    print(f"\n[*] Downloading remaining batches...")

    while current_pos < last_toc_pos:
        try:
            print(f"\n[*] Batch {batch_num}: position {current_pos}...")
            tar_data = downloader.render_pages(asin, revision, start_position=current_pos, num_pages=5)
            files = downloader.extract_tar(tar_data, output_base / f'batch_{batch_num}')

            # Get end position from this batch
            page_file = list((output_base / f'batch_{batch_num}').glob('page_data_*.json'))[0]
            with open(page_file) as f:
                pages = json.load(f)

            if pages:
                batch_end = pages[-1]['endPositionId']
                print(f"[✓] Batch {batch_num}: {pages[0]['startPositionId']} to {batch_end}")
                current_pos = batch_end + 1
            else:
                print(f"[!] Batch {batch_num}: No pages returned, stopping")
                break

            batch_num += 1

        except Exception as e:
            print(f"[✗] Error downloading batch {batch_num}: {e}")
            break

    print(f"\n{'='*80}")
    print(f"[✓] DOWNLOAD COMPLETE")
    print(f"[✓] Downloaded {batch_num} batches")
    print(f"[✓] Saved to: {output_base}/")
    print(f"{'='*80}\n")

    # Save download metadata
    download_info = {
        'asin': asin,
        'revision': revision,
        'start_position': start_pos,
        'total_batches': batch_num,
        'pages_per_batch': 5,
        'estimated_positions': f'{start_pos} to {current_pos}'
    }

    with open(output_base / 'download_info.json', 'w') as f:
        json.dump(download_info, f, indent=2)

if __name__ == '__main__':
    main()
