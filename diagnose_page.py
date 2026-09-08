"""Diagnostic script to verify block merging fix."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import fitz
from app.parsing.pdf_parser import PDFParser
from app.extraction.candidate_detector import CandidateDetector

pdf_path = r'c:\Users\abys7\Downloads\superjoin final\uploads\7f35d283_02-rbi-annual-report-2024-25-excerpt.pdf'
doc = fitz.open(pdf_path)
parser = PDFParser()
detector = CandidateDetector()

# Page 66 = index 65 (the equity market page with charts + multi-column text)
target_page = 65
fitz_page = doc[target_page]
parsed_page = parser._parse_page(fitz_page, target_page + 1)

print(f'=== PAGE {target_page+1} (AFTER MERGE FIX) ===')
print(f'Dimensions: {parsed_page.width} x {parsed_page.height}')
print(f'Total blocks: {len(parsed_page.blocks)}')
print(f'Tables: {len(parsed_page.tables)}')
print()

# Show parsed blocks
for b in parsed_page.blocks:
    content_preview = b.content[:100].replace('\n', ' ')
    score = detector.score_block(b)
    marker = "CANDIDATE" if score >= detector.THRESHOLD else "REJECTED"
    print(f'[{marker} {score:.2f}] type={b.block_type:12s} len={len(b.content):4d} bbox=({b.bbox[0]:.0f},{b.bbox[1]:.0f},{b.bbox[2]:.0f},{b.bbox[3]:.0f})')
    print(f'  "{content_preview}"')
    print()

# Also test another page with different layout
print('\n' + '='*60)
print('Testing page 1 (cover/title page)...')
p1 = parser._parse_page(doc[0], 1)
print(f'Page 1 blocks: {len(p1.blocks)}')
for b in p1.blocks:
    print(f'  type={b.block_type:12s} len={len(b.content):4d} "{b.content[:60].replace(chr(10), " ")}"')

# Test a page with tables
for i in range(doc.page_count):
    p = parser._parse_page(doc[i], i+1)
    if p.tables:
        print(f'\nPage {i+1} has {len(p.tables)} tables and {len(p.blocks)} blocks')
        for b in p.blocks[:5]:
            print(f'  type={b.block_type:12s} len={len(b.content):4d} "{b.content[:60].replace(chr(10), " ")}"')
        break

doc.close()
print('\nDONE')
