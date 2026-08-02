"""
Weekly summary report generator.
Reads the latest output CSV and writes a DOCX report with:
  - Run metadata (date range, total jobs)
  - Jobs by platform
  - Jobs by category
  - Jobs by state
  - Top 10 hiring facilities
"""
import os
import glob
import logging
from datetime import datetime

import pandas as pd
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


logger = logging.getLogger("report")


# ── Helpers ─────────────────────────────────────────────────────────────────

def _set_cell_bg(cell, hex_color: str):
    """Shades a table cell with a hex fill colour (e.g. '4472C4')."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def _header_row(table, labels: list, bg: str = '2E74B5'):
    """Writes bold white header cells into row 0 of *table*."""
    row = table.rows[0]
    for i, label in enumerate(labels):
        cell = row.cells[i]
        cell.text = label
        _set_cell_bg(cell, bg)
        run = cell.paragraphs[0].runs[0]
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        run.font.size = Pt(10)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER


def _add_table(doc: Document, df: pd.DataFrame, col_widths: list = None):
    """Adds a styled table to *doc* from a DataFrame (index included as first col)."""
    df = df.reset_index()
    rows, cols = df.shape
    table = doc.add_table(rows=rows + 1, cols=cols)
    table.style = 'Table Grid'

    _header_row(table, list(df.columns))

    for r_idx, row in df.iterrows():
        tr = table.rows[r_idx + 1]
        for c_idx, val in enumerate(row):
            cell = tr.cells[c_idx]
            cell.text = str(val)
            cell.paragraphs[0].runs[0].font.size = Pt(10)
            if r_idx % 2 == 0:
                _set_cell_bg(cell, 'DEEAF1')

    if col_widths:
        for col_i, width in enumerate(col_widths):
            for cell in table.columns[col_i].cells:
                cell.width = Inches(width)

    doc.add_paragraph()  # spacing after table


# ── Main report function ─────────────────────────────────────────────────────

def generate_report(base_dir: str = ".", csv_path: str = None) -> str:
    """
    Generates a DOCX weekly summary report.

    Args:
        base_dir:  project root (used to locate output/ and logs/).
        csv_path:  explicit CSV to use; if None, the latest output CSV is used.

    Returns:
        Path to the generated DOCX file.
    """
    output_dir = os.path.join(base_dir, "output")

    # Find CSV
    if csv_path is None:
        pattern = os.path.join(output_dir, "healthcare_jobs_report_*.csv")
        matches = sorted(glob.glob(pattern))
        if not matches:
            raise FileNotFoundError(f"No output CSV found in {output_dir}")
        csv_path = matches[-1]

    logger.info(f"Building report from: {csv_path}")
    df = pd.read_csv(csv_path)

    # ── Document setup ──────────────────────────────────────────────────────
    doc = Document()

    # Page margins (narrower for tables)
    for section in doc.sections:
        section.top_margin    = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin   = Inches(1)
        section.right_margin  = Inches(1)

    # ── Title block ─────────────────────────────────────────────────────────
    title = doc.add_heading('Healthcare Jobs — Weekly Summary Report', level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Date range from the data
    dates = pd.to_datetime(df['Date Posted'], errors='coerce').dropna()
    if not dates.empty:
        date_min = dates.min().strftime('%d %b %Y')
        date_max = dates.max().strftime('%d %b %Y')
        date_range = f"{date_min} – {date_max}"
    else:
        date_range = "N/A"

    run_date = datetime.now().strftime('%d %b %Y %H:%M')

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(f"Report generated: {run_date}    |    Posting date range: {date_range}    |    "
                 f"Total jobs: {len(df):,}").font.size = Pt(10)

    doc.add_paragraph()

    # ── Section 1: Jobs by Platform ─────────────────────────────────────────
    doc.add_heading('1. Jobs by Platform', level=1)
    platform_df = (
        df.groupby('Platform')
          .size()
          .rename('Job Count')
          .sort_values(ascending=False)
    )
    _add_table(doc, platform_df.to_frame(), col_widths=[2.5, 1.5])

    # ── Section 2: Jobs by Category ─────────────────────────────────────────
    doc.add_heading('2. Jobs by Category', level=1)
    cat_df = (
        df.groupby('Job Category')
          .size()
          .rename('Job Count')
          .sort_values(ascending=False)
    )
    _add_table(doc, cat_df.to_frame(), col_widths=[2.5, 1.5])

    # ── Section 3: Jobs by State ─────────────────────────────────────────────
    doc.add_heading('3. Jobs by State', level=1)
    state_df = (
        df.groupby('State')
          .size()
          .rename('Job Count')
          .sort_values(ascending=False)
    )
    _add_table(doc, state_df.to_frame(), col_widths=[1.5, 1.5])

    # ── Section 4: Platform × State cross-tab ───────────────────────────────
    doc.add_heading('4. Platform × State Breakdown', level=1)
    pivot = (
        df.groupby(['Platform', 'State'])
          .size()
          .unstack(fill_value=0)
    )
    # Sort columns by total descending
    pivot = pivot[pivot.sum().sort_values(ascending=False).index]
    _add_table(doc, pivot)

    # ── Section 5: Top 10 Facilities ────────────────────────────────────────
    doc.add_heading('5. Top 10 Hiring Facilities', level=1)
    top10 = (
        df[df['Facility Name'].str.lower() != 'unknown facility']
          .groupby('Facility Name')
          .size()
          .rename('Job Count')
          .sort_values(ascending=False)
          .head(10)
    )
    _add_table(doc, top10.to_frame(), col_widths=[3.5, 1.5])

    # ── Section 6: Top 10 Facilities per Category ───────────────────────────
    doc.add_heading('6. Top Facilities by Category', level=1)
    for category in sorted(df['Job Category'].unique()):
        sub = df[
            (df['Job Category'] == category) &
            (df['Facility Name'].str.lower() != 'unknown facility')
        ]
        if sub.empty:
            continue
        doc.add_heading(category, level=2)
        top_cat = (
            sub.groupby('Facility Name')
               .size()
               .rename('Job Count')
               .sort_values(ascending=False)
               .head(5)
        )
        _add_table(doc, top_cat.to_frame(), col_widths=[3.5, 1.5])

    # ── Facility Summary CSV export ──────────────────────────────────────────
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')

    facility_summary = (
        df[df['Facility Name'].str.lower() != 'unknown facility']
          .groupby(['Facility Name', 'State', 'Job Category'])
          .size()
          .rename('Job Count')
          .reset_index()
          .sort_values(['Job Count', 'Facility Name'], ascending=[False, True])
    )
    facility_csv_path = os.path.join(output_dir, f'facility_summary_{timestamp}.csv')
    facility_summary.to_csv(facility_csv_path, index=False, encoding='utf-8')
    logger.info(f"Facility summary CSV saved: {facility_csv_path}")

    # ── Save DOCX ────────────────────────────────────────────────────────────
    docx_path = os.path.join(output_dir, f'healthcare_jobs_summary_{timestamp}.docx')
    doc.save(docx_path)
    logger.info(f"Report saved: {docx_path}")
    return docx_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    path = generate_report(base_dir=".")
    print(f"Report: {path}")
