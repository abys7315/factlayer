"""
Generate synthetic test PDFs covering the four fundamental evaluation cases:
1. Case 1: Corroborating Facts across documents
2. Case 2: Temporal Supersession (fact update across fiscal periods/revisions)
3. Case 3: Genuine Contradiction (conflicting claims for the same entity, attribute, and timeframe)
4. Case 4: Contextual Non-Contradiction (differing accounting scopes or regional scopes)
"""

import os
from pathlib import Path
import fitz  # PyMuPDF

OUTPUT_DIR = Path(__file__).parent / "synthetic"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_pdf(filename: str, title: str, pages_content: list[list[str]]):
    doc = fitz.open()
    for page_lines in pages_content:
        page = doc.new_page(width=595, height=842)  # A4
        y = 50
        # Title
        page.insert_text((50, y), title, fontsize=16, fontname="helv", color=(0.1, 0.1, 0.3))
        y += 40

        for line in page_lines:
            if line.startswith("## "):
                y += 10
                page.insert_text((50, y), line[3:], fontsize=13, color=(0.2, 0.2, 0.5))
                y += 25
            elif line.startswith("|"):
                page.insert_text((50, y), line, fontsize=9, color=(0.15, 0.15, 0.15))
                y += 16
            else:
                page.insert_text((50, y), line, fontsize=10, color=(0.1, 0.1, 0.1))
                y += 18
            if y > 780:
                break
    target_path = OUTPUT_DIR / filename
    doc.save(str(target_path))
    doc.close()
    print(f"Generated synthetic PDF: {target_path}")


def main():
    # ── Doc A1: Acme Corp 2023 Annual Report ──
    create_pdf(
        "acme_annual_report_2023.pdf",
        "Acme Technologies Inc. — 2023 Annual Report",
        [
            [
                "## Executive Summary",
                "Acme Technologies Inc. (NYSE: ACM) achieved record performance in fiscal year 2023.",
                "Chief Executive Officer: Jane Doe.",
                "Total Full-Year Revenue: $100,000,000 ($100M USD) for the fiscal year ended December 31, 2023.",
                "Headquarters: San Francisco, California.",
                "Full-Time Employee Headcount: 450 employees as of year end.",
                "",
                "## Financial Highlights",
                "| Metric                  | FY 2022        | FY 2023        |",
                "| Total Revenue           | $80,000,000    | $100,000,000   |",
                "| Net Income (GAAP)       | $12,000,000    | $18,000,000    |",
                "| Operating Margin        | 15.0%          | 18.0%          |",
            ]
        ]
    )

    # ── Doc A2: Acme Corp Press Release FY23 (Case 1: Exact Corroboration) ──
    create_pdf(
        "acme_fy23_press_release.pdf",
        "Press Release: Acme Technologies Reports Fiscal 2023 Results",
        [
            [
                "## For Immediate Release — February 15, 2024",
                "Acme Technologies Inc. today reported record annual revenue of $100 million for fiscal year 2023.",
                "CEO Jane Doe stated that strong demand across enterprise cloud solutions drove 25% year-over-year revenue expansion.",
                "Acme closed 2023 with 450 full-time team members worldwide.",
            ]
        ]
    )

    # ── Doc B1: Acme Corp 2024 Annual Report (Case 2: Supersedes FY23 -> FY24) ──
    create_pdf(
        "acme_annual_report_2024.pdf",
        "Acme Technologies Inc. — 2024 Annual Report",
        [
            [
                "## Executive Summary",
                "Acme Technologies Inc. continued its rapid expansion through fiscal year 2024.",
                "Chief Executive Officer: John Smith (appointed July 2024, succeeding Jane Doe).",
                "Total Full-Year Revenue: $140,000,000 ($140M USD) for the fiscal year ended December 31, 2024.",
                "Global Headcount: 620 full-time employees.",
                "",
                "## Two-Year Comparison",
                "| Metric                  | FY 2023        | FY 2024        |",
                "| Total Revenue           | $100,000,000   | $140,000,000   |",
                "| Net Income (GAAP)       | $18,000,000    | $26,000,000    |",
            ]
        ]
    )

    # ── Doc C1: Competitor / Leaked Analyst Report (Case 3: Genuine Contradiction on FY23) ──
    create_pdf(
        "acme_analyst_disputed_report_2023.pdf",
        "Market Analyst Report — Acme Technologies 2023 Discrepancy Note",
        [
            [
                "## Independent Audit Note",
                "According to restated forensic analysis, Acme Technologies Inc. achieved total full-year revenue of only $85,000,000 in fiscal year 2023.",
                "The previously claimed $100M revenue figure contained unearned deferred software licenses.",
                "Total Full-Year Revenue: $85,000,000 for the fiscal year ended December 31, 2023.",
            ]
        ]
    )

    # ── Doc D1: Segment & Non-GAAP Disclosure (Case 4: Contextual Non-Contradiction) ──
    create_pdf(
        "acme_non_gaap_segment_report_2023.pdf",
        "Acme Technologies Inc. — Supplemental Segment & Non-GAAP Disclosures FY23",
        [
            [
                "## Non-GAAP & Regional Revenue Breakdowns",
                "North America Regional Revenue: $65,000,000 for fiscal year 2023.",
                "International (EMEA + APAC) Regional Revenue: $35,000,000 for fiscal year 2023.",
                "Adjusted Non-GAAP Net Income (excluding stock-based compensation): $24,000,000 for fiscal year 2023.",
                "(Note: GAAP Net Income remains $18,000,000; non-GAAP adjustments add $6,000,000).",
            ]
        ]
    )


if __name__ == "__main__":
    main()
