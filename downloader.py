#!/usr/bin/env python3
"""
Kindle Book Downloader
Downloads raw page data from Kindle Cloud Reader (Stage 1)

Usage:
    python3 downloader.py <ASIN> [--pages N] [--output DIR]

Example:
    python3 downloader.py B0FLBTR2FS --pages 10 --output downloads/
"""
import requests
import json
import tarfile
import io
import sys
import argparse
from pathlib import Path

class KindleDownloader:
    """Downloads raw encrypted book data from Kindle Cloud Reader"""

    def __init__(self, cookies_string, adp_session_token=None):
        """
        Initialize with authentication credentials

        Args:
            cookies_string: Cookie string from browser
            adp_session_token: x-adp-session-token header value
        """
        self.session = requests.Session()

        # Parse cookies
        for cookie in cookies_string.split('; '):
            if '=' in cookie:
                name, value = cookie.split('=', 1)
                self.session.cookies.set(name, value, domain='.amazon.com')

        self.adp_session_token = adp_session_token
        self.rendering_token = None
        self.token_expires = None

    def start_reading(self, asin):
        """
        Initialize reading session and get rendering token

        Args:
            asin: Book ASIN

        Returns:
            dict: Book metadata including token, revision, srl
        """
        url = 'https://read.amazon.com/service/mobile/reader/startReading'
        params = {
            'asin': asin,
            'clientVersion': '20000100'
        }

        headers = {}
        if self.adp_session_token:
            headers['x-adp-session-token'] = self.adp_session_token

        print(f"[*] Requesting reading session for {asin}...")
        response = self.session.get(url, params=params, headers=headers)
        response.raise_for_status()

        data = response.json()

        # Store token
        if 'karamelToken' in data:
            self.rendering_token = data['karamelToken']['token']
            self.token_expires = data['karamelToken']['expiresAt']
            print(f"[✓] Got rendering token (expires: {self.token_expires})")

        return data

    def render_pages(self, asin, revision, start_position=0, num_pages=2):
        """
        Download raw page data from Kindle renderer

        Args:
            asin: Book ASIN
            revision: Content revision ID
            start_position: Starting position ID
            num_pages: Number of pages to fetch

        Returns:
            bytes: Raw TAR archive containing page data
        """
        url = 'https://read.amazon.com/renderer/render'

        params = {
            'version': '3.0',
            'asin': asin,
            'contentType': 'FullBook',
            'revision': revision,
            'fontFamily': 'Bookerly',
            'fontSize': '8.91',
            'lineHeight': '1.4',
            'dpi': '160',
            'height': '1600',
            'width': '1000',
            'marginBottom': '0',
            'marginLeft': '9',
            'marginRight': '9',
            'marginTop': '0',
            'maxNumberColumns': '1',
            'theme': 'dark',
            'locationMap': 'false',
            'packageType': 'TAR',
            'encryptionVersion': 'NONE',
            'numPage': str(num_pages),
            'skipPageCount': '0',
            'startingPosition': str(start_position),
            'bundleImages': 'false'
        }

        headers = {
            'x-amz-rendering-token': self.rendering_token
        }

        print(f"[*] Downloading {num_pages} pages from position {start_position}...")
        response = self.session.get(url, params=params, headers=headers)

        if response.status_code != 200:
            print(f"[✗] Error {response.status_code}: {response.text[:200]}")

        response.raise_for_status()

        return response.content

    def extract_tar(self, tar_bytes, output_dir):
        """
        Extract TAR archive to directory

        Args:
            tar_bytes: Raw TAR data
            output_dir: Directory to extract to

        Returns:
            list: Names of extracted files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        extracted_files = []

        with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
            for member in tar.getmembers():
                if member.isfile():
                    content = tar.extractfile(member).read()
                    file_path = output_path / member.name
                    # Create parent directories if they don't exist
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_bytes(content)
                    extracted_files.append(member.name)

        return extracted_files

    def download(self, asin, num_pages=2, output_dir=None):
        """
        Download book pages and save raw data

        Args:
            asin: Book ASIN
            num_pages: Number of pages to download
            output_dir: Output directory (default: downloads/<asin>/)

        Returns:
            dict: Download metadata
        """
        print(f"\n{'='*80}")
        print(f"KINDLE DOWNLOADER")
        print(f"{'='*80}\n")

        # Get metadata and token
        metadata = self.start_reading(asin)

        title = metadata.get('deliveredAsin', asin)
        revision = metadata.get('contentVersion', '')
        srl = metadata.get('srl', 0)

        print(f"[*] ASIN: {title}")
        print(f"[*] Revision: {revision}")
        print(f"[*] SRL (start position): {srl}")

        # Download pages
        tar_data = self.render_pages(asin, revision, start_position=srl, num_pages=num_pages)
        print(f"[✓] Downloaded {len(tar_data)} bytes")

        # Extract to directory
        if output_dir is None:
            output_dir = f"downloads/{asin}"

        print(f"[*] Extracting to {output_dir}/...")
        extracted_files = self.extract_tar(tar_data, output_dir)
        print(f"[✓] Extracted {len(extracted_files)} files:")
        for filename in extracted_files:
            print(f"    - {filename}")

        # Save metadata
        metadata_file = Path(output_dir) / 'download_metadata.json'
        download_info = {
            'asin': asin,
            'revision': revision,
            'srl': srl,
            'start_position': srl,
            'num_pages': num_pages,
            'extracted_files': extracted_files
        }
        metadata_file.write_text(json.dumps(download_info, indent=2))
        print(f"[✓] Saved metadata to {metadata_file}")

        print(f"\n{'='*80}")
        print(f"[✓] DOWNLOAD COMPLETE")
        print(f"[✓] Data saved to: {output_dir}/")
        print(f"{'='*80}\n")

        return download_info

def main():
    parser = argparse.ArgumentParser(
        description='Download raw page data from Kindle Cloud Reader',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 downloader.py B0FLBTR2FS
  python3 downloader.py B0FLBTR2FS --pages 10
  python3 downloader.py B0FLBTR2FS --output my_books/
        """
    )
    parser.add_argument('asin', help='Book ASIN to download')
    parser.add_argument('--pages', type=int, default=2, help='Number of pages to download (default: 2)')
    parser.add_argument('--output', help='Output directory (default: downloads/<asin>/)')
    parser.add_argument('--start-position', type=int, help='Override start position (default: use SRL from metadata)')

    args = parser.parse_args()

    # Load credentials from headers.json
    headers_file = Path('headers.json')
    if not headers_file.exists():
        print("[✗] headers.json not found!")
        print("\nCreate headers.json with:")
        print('  {')
        print('    "headers": {"x-adp-session-token": "..."},')
        print('    "cookies": "session-id=...; ..."')
        print('  }')
        sys.exit(1)

    with open(headers_file) as f:
        headers_data = json.load(f)

    cookies = headers_data.get('cookies', '')
    if not cookies:
        print("[✗] No cookies found in headers.json!")
        sys.exit(1)

    adp_token = None
    if 'headers' in headers_data:
        adp_token = headers_data['headers'].get('x-adp-session-token')

    # Download
    downloader = KindleDownloader(cookies, adp_token)

    # Override start position if specified
    if args.start_position is not None:
        metadata = downloader.start_reading(args.asin)
        revision = metadata.get('contentVersion', '')

        # Download from custom position
        tar_data = downloader.render_pages(args.asin, revision, start_position=args.start_position, num_pages=args.pages)

        # Extract
        output_dir = args.output or f"downloads/{args.asin}"
        print(f"[*] Extracting to {output_dir}/...")
        extracted_files = downloader.extract_tar(tar_data, output_dir)
        print(f"[✓] Extracted {len(extracted_files)} files")
    else:
        downloader.download(args.asin, num_pages=args.pages, output_dir=args.output)

if __name__ == '__main__':
    main()
