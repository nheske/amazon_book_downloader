# Download the complete book (replace B0FLBTR2FS with your ASIN)
python download_full_book.py B00O87R6US --yes
# Decode the glyphs (replace B0FLBTR2FS with your ASIN)
python decode_glyphs_complete.py downloads/B00O87R6US --progressive
# Create the EPUB file
python create_epub.py downloads/B00O87R6US

Get Fresh Authentication
Open your browser and go to https://read.amazon.com
Make sure you're logged in to your Amazon account
Open Developer Tools (F12)
Go to Network tab and clear it
Refresh the page or click on a book to trigger network requests
Look for requests to read.amazon.com (especially startReading or similar)
Click on one of these requests
Copy the Request Headers:
Find Cookie: and copy the entire value
Find x-adp-session-token: and copy its value
Update Your headers.json
You need to replace your current credentials with fresh ones. The format should be:

Important: The cookies and token must be from an active browser session where you can successfully read books on read.amazon.com. If you can't read books in your browser, the credentials won't work for the downloader either.

Use WSL/Linux approach - it will give you much better results because:

# Cairo for SVG generation not working on Windows
Cairo works properly on Linux
SVG rendering is more accurate
Character matching will be much better (typically 95%+ success rate)
You'll get the full 281-page book instead of a 1-page stub
The Windows workaround was a good attempt, but the fundamental issue is that matplotlib's SVG rendering isn't accurate enough for the precise glyph matching needed for this reverse-engineering task.

# Using Ubuntu on WSL
Distribution successfully installed. It can be launched via 'wsl.exe -d Ubuntu'
Launching Ubuntu...
Provisioning the new WSL instance Ubuntu
This might take a while...
Create a default Unix user account: normh
password: password



wsl -d Ubuntu
# Update package list
sudo apt update

# Install Cairo and development tools
sudo apt install -y python3-pip libcairo2-dev pkg-config python3-dev

# Install Python packages
pip3 install pillow cairosvg imagehash svgpathtools fonttools scikit-image tqdm ebooklib



Step 1: Create a Virtual Environment
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate
Step 2: Install the Python Packages
# Now install the packages in the virtual environment
pip install pillow cairosvg imagehash svgpathtools fonttools scikit-image tqdm ebooklib
Step 3: Run the Decoding Script
# Run the original script with proper Cairo support
python decode_glyphs_complete.py downloads/B00O87R6US --progressive

This approach:

✅ Creates an isolated environment so we don't break the system Python
✅ Allows pip installations without the externally-managed error
✅ Uses proper Cairo libraries for accurate SVG rendering
✅ Should give you 95%+ character matching instead of the 34% from Windows
After you activate the virtual environment (you'll see (venv) in your prompt), you can run all the Python commands normally and they'll use the packages installed in the virtual environment.

The virtual environment approach is actually the recommended best practice for Python development, so this is perfect!