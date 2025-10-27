import json

# Load TOC
with open('downloads/B07TM8LMRW/batch_0/toc.json') as f:
    toc = json.load(f)

print(f"Total TOC entries: {len(toc)}")
print("\nTOC entries:")
for i, entry in enumerate(toc):
    print(f"{i}: {entry['label']} -> position {entry['tocPositionId']}")