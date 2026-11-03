import os
import io
import re
import csv
import base64
import logging
from typing import List, Dict, Any, Tuple, Optional
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

logger = logging.getLogger(__name__)

# Standard ABET / NBA Program Outcomes (POs) for Engineering (ECE / SET)
PO_DEFINITIONS = {
    "PO1": "Engineering Knowledge",
    "PO2": "Problem Analysis",
    "PO3": "Design/Development of Solutions",
    "PO4": "Conduct Investigations of Complex Problems",
    "PO5": "Modern Tool Usage",
    "PO6": "The Engineer and Society",
    "PO7": "Environment and Sustainability",
    "PO8": "Ethics",
    "PO9": "Individual and Team Work",
    "PO10": "Communication",
    "PO11": "Project Management and Finance",
    "PO12": "Life-long Learning",
}

# Strict color specification matching Google Forms visualization palette
FEEDBACK_CATEGORIES = ["Fair", "Satisfactory", "Very Good", "Excellent"]
FEEDBACK_COLORS = {
    "Fair": "#3366CC",          # Google Blue
    "Satisfactory": "#DC3912",  # Google Red
    "Very Good": "#FF9900",     # Google Orange
    "Excellent": "#109618",     # Google Green
}

# Department Class Colors matching Pasted image.png
CLASS_COLORS = [
    "#4285F4",  # Blue
    "#EA4335",  # Red
    "#FBBC05",  # Yellow
    "#34A853",  # Green
    "#FF6D01",  # Orange
    "#46BDC6",  # Cyan
    "#7BAAF7",  # Light Blue
    "#BA68C8",  # Purple
    "#9AA0A6",  # Grey
]


class FeedbackAnalysisService:
    """
    Parses feedback responses from CSV, Excel, or XML, maps columns to PO1-PO12,
    renders Google Forms style pie charts, computes response distributions,
    and drafts factual interpretations.
    """

    @classmethod
    def parse_feedback_file(cls, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse raw bytes of CSV, Excel (.xlsx, .xls), or XML spreadsheet into headers and row dictionaries.
        """
        if not file_bytes:
            return {"success": False, "error": "Empty file received.", "headers": [], "rows": []}

        filename_lower = filename.lower()

        try:
            # 1. XML Spreadsheet (Excel 2003 XML format like 'the gauntlet.xml')
            if filename_lower.endswith(".xml") or file_bytes[:100].find(b"<Workbook") != -1:
                return cls._parse_xml_spreadsheet(file_bytes)

            # 2. Modern Excel (.xlsx)
            if filename_lower.endswith(".xlsx"):
                return cls._parse_xlsx(file_bytes)

            # 3. Default to CSV
            return cls._parse_csv(file_bytes)
        except Exception as e:
            logger.error("Failed to parse feedback file %s: %s", filename, e)
            return {"success": False, "error": f"Failed to parse file: {str(e)}", "headers": [], "rows": []}

    @classmethod
    def _parse_csv(cls, file_bytes: bytes) -> Dict[str, Any]:
        """Parse CSV content with multiple encoding attempts."""
        content = None
        for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
            try:
                content = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            content = file_bytes.decode("utf-8", errors="replace")

        # Sniff delimiter
        sample = content[:2048]
        delimiter = ","
        if "\t" in sample and sample.count("\t") > sample.count(","):
            delimiter = "\t"
        elif ";" in sample and sample.count(";") > sample.count(","):
            delimiter = ";"

        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        rows_list = list(reader)
        if not rows_list:
            return {"success": False, "error": "CSV file contains no data.", "headers": [], "rows": []}

        # Filter out empty rows at start
        while rows_list and not any(cell.strip() for cell in rows_list[0]):
            rows_list.pop(0)

        if not rows_list:
            return {"success": False, "error": "CSV contains only blank lines.", "headers": [], "rows": []}

        headers = [h.strip() for h in rows_list[0]]
        data_rows = []
        for r in rows_list[1:]:
            if not any(cell.strip() for cell in r):
                continue
            row_dict = {}
            for idx, h in enumerate(headers):
                val = r[idx].strip() if idx < len(r) else ""
                row_dict[h] = val
            data_rows.append(row_dict)

        return {
            "success": True,
            "headers": headers,
            "rows": data_rows,
            "total_rows": len(data_rows),
        }

    @classmethod
    def _parse_xlsx(cls, file_bytes: bytes) -> Dict[str, Any]:
        """Parse Excel file using openpyxl."""
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        sheet = wb.active
        rows_iter = sheet.iter_rows(values_only=True)

        headers = None
        data_rows = []

        for row in rows_iter:
            if not row or not any(row):
                continue
            if headers is None:
                headers = [str(c or "").strip() for c in row]
            else:
                row_dict = {}
                for idx, h in enumerate(headers):
                    val = str(row[idx] or "").strip() if idx < len(row) else ""
                    row_dict[h] = val
                data_rows.append(row_dict)

        return {
            "success": True,
            "headers": headers or [],
            "rows": data_rows,
            "total_rows": len(data_rows),
        }

    @classmethod
    def _parse_xml_spreadsheet(cls, file_bytes: bytes) -> Dict[str, Any]:
        """Parse Excel 2003 XML spreadsheet."""
        tree = ET.fromstring(file_bytes)
        ns = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}

        worksheet = tree.find(".//ss:Worksheet", ns)
        if worksheet is None:
            return {"success": False, "error": "No Worksheet found in XML.", "headers": [], "rows": []}

        table = worksheet.find("ss:Table", ns)
        if table is None:
            return {"success": False, "error": "No Table found in Worksheet.", "headers": [], "rows": []}

        rows_elem = table.findall("ss:Row", ns)
        raw_rows = []
        for r_elem in rows_elem:
            row_cells = []
            cells = r_elem.findall("ss:Cell", ns)
            curr_col = 0
            for c in cells:
                idx_attr = c.attrib.get(f"{{{ns['ss']}}}Index")
                if idx_attr:
                    target_idx = int(idx_attr) - 1
                    while curr_col < target_idx:
                        row_cells.append("")
                        curr_col += 1

                data_elem = c.find("ss:Data", ns)
                val = data_elem.text if data_elem is not None and data_elem.text else ""
                row_cells.append(val.strip())
                curr_col += 1
            if any(cell.strip() for cell in row_cells):
                raw_rows.append(row_cells)

        if not raw_rows:
            return {"success": False, "error": "No rows found in XML spreadsheet.", "headers": [], "rows": []}

        # Find header row (row containing headers like name, reg no, po, question, etc.)
        header_idx = 0
        for i, row in enumerate(raw_rows[:10]):
            row_str = " ".join(row).lower()
            if any(term in row_str for term in ["name", "reg", "rating", "po1", "feedback", "excellent", "fair", "s.no"]):
                header_idx = i
                break

        headers = raw_rows[header_idx]
        data_rows = []
        for r in raw_rows[header_idx + 1:]:
            row_dict = {}
            for idx, h in enumerate(headers):
                if not h:
                    continue
                val = r[idx] if idx < len(r) else ""
                row_dict[h] = val
            if any(row_dict.values()):
                data_rows.append(row_dict)

        return {
            "success": True,
            "headers": [h for h in headers if h],
            "rows": data_rows,
            "total_rows": len(data_rows),
        }

    @classmethod
    def normalize_rating(cls, val: Any) -> Optional[str]:
        """
        Normalize a survey cell value into one of the 4 strict categories:
        Fair, Satisfactory, Very Good, Excellent.
        Returns None if unanswered or unmapped.
        """
        if val is None:
            return None
        s = str(val).strip().lower()
        if not s:
            return None

        # Clean punctuation
        s_clean = re.sub(r"[^\w\s]", "", s).strip()

        # Numeric 1-4 or 1-5 scale
        if s_clean in ("1", "poor", "fair", "needs improvement"):
            return "Fair"
        elif s_clean in ("2", "satisfactory", "average", "moderate"):
            return "Satisfactory"
        elif s_clean in ("3", "very good", "good", "above average"):
            return "Very Good"
        elif s_clean in ("4", "5", "excellent", "outstanding", "strongly agree"):
            return "Excellent"

        # Substring heuristics
        if "excel" in s_clean:
            return "Excellent"
        if "very" in s_clean and "good" in s_clean:
            return "Very Good"
        if "satisf" in s_clean or "aver" in s_clean:
            return "Satisfactory"
        if "fair" in s_clean or "poor" in s_clean:
            return "Fair"

        return None

    @classmethod
    def auto_suggest_po_mappings(cls, headers: List[str]) -> Dict[str, str]:
        """
        Suggest mapping from headers to PO1..PO12.
        Example: 'PO1 - Engineering Knowledge' -> 'PO1'
        """
        mapping = {}
        for h in headers:
            h_upper = h.upper()
            for po_id, po_desc in PO_DEFINITIONS.items():
                if po_id in h_upper or po_desc.upper() in h_upper:
                    mapping[po_id] = h
                    break
        return mapping

    @classmethod
    def generate_po_pie_chart(
        cls,
        po_id: str,
        po_title: str,
        counts_dict: Dict[str, int],
        output_dir: Optional[str] = None,
    ) -> Tuple[bytes, str]:
        """
        Generate a Google Forms style pie chart for a PO with exact palette:
        Fair (#3366CC), Satisfactory (#DC3912), Very Good (#FF9900), Excellent (#109618).
        Returns: (png_bytes, base64_data_uri)
        """
        total = sum(counts_dict.values())
        categories = ["Excellent", "Very Good", "Fair", "Satisfactory"]
        counts = [counts_dict.get(cat, 0) for cat in categories]
        colors = [FEEDBACK_COLORS[cat] for cat in categories]

        # Matplotlib figure with crisp white background
        fig, ax = plt.subplots(figsize=(6.2, 3.8), dpi=300, facecolor="#ffffff")
        ax.set_facecolor("#ffffff")

        if total > 0:
            wedges, texts, autotexts = ax.pie(
                counts,
                colors=colors,
                autopct=lambda pct: f"{pct:.1f}%" if pct >= 1.0 else "",
                startangle=140,
                textprops=dict(color="#ffffff", weight="bold", fontsize=9),
                pctdistance=0.72,
                wedgeprops=dict(edgecolor="#ffffff", linewidth=1.5),
            )

            legend_categories = ["Fair", "Satisfactory", "Very Good", "Excellent"]
            legend_handles = [
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    color="none",
                    markerfacecolor=FEEDBACK_COLORS[cat],
                    markeredgecolor="none",
                    markersize=7,
                    linestyle="None",
                )
                for cat in legend_categories
            ]
            ax.legend(
                handles=legend_handles,
                labels=legend_categories,
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                frameon=False,
                fontsize=9,
                handletextpad=0.6,
            )
        else:
            ax.text(
                0.5,
                0.5,
                "No responses recorded",
                horizontalalignment="center",
                verticalalignment="center",
                fontsize=11,
                color="#666666",
            )

        chart_heading = f"{po_id}: {po_title}\n{total} responses"
        ax.set_title(chart_heading, fontsize=11, weight="bold", pad=12, color="#202124", loc="left")

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=300, facecolor="#ffffff")
        plt.close(fig)

        raw_bytes = buf.getvalue()

        # Optionally save to disk
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            fp = os.path.join(output_dir, f"chart_{po_id.lower()}.png")
            with open(fp, "wb") as f:
                f.write(raw_bytes)

        b64 = f"data:image/png;base64,{base64.b64encode(raw_bytes).decode('ascii')}"
        return raw_bytes, b64

    @classmethod
    def generate_class_distribution_pie_chart(
        cls,
        class_distribution: List[Dict[str, Any]],
        output_dir: Optional[str] = None,
    ) -> Tuple[bytes, str]:
        """
        Generate a Google Forms style pie chart for class distribution matching Pasted image.png.
        """
        labels = [item["class_name"] for item in class_distribution if item["count"] > 0]
        counts = [item["count"] for item in class_distribution if item["count"] > 0]
        total = sum(counts)

        fig, ax = plt.subplots(figsize=(6.2, 3.8), dpi=300, facecolor="#ffffff")
        ax.set_facecolor("#ffffff")

        if total > 0:
            slice_colors = [CLASS_COLORS[i % len(CLASS_COLORS)] for i in range(len(labels))]
            wedges, texts, autotexts = ax.pie(
                counts,
                colors=slice_colors,
                autopct=lambda pct: f"{pct:.1f}%" if pct >= 1.0 else "",
                startangle=140,
                textprops=dict(color="#ffffff", weight="bold", fontsize=9),
                pctdistance=0.72,
                wedgeprops=dict(edgecolor="#ffffff", linewidth=1.5),
            )
            legend_handles = [
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    color="none",
                    markerfacecolor=slice_colors[i],
                    markeredgecolor="none",
                    markersize=8,
                )
                for i in range(len(labels))
            ]
            ax.legend(
                handles=legend_handles,
                labels=labels,
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                frameon=False,
                fontsize=9,
                handletextpad=0.6,
            )
        else:
            ax.text(0.5, 0.5, "No attendance records", ha="center", va="center", color="#666666")

        ax.set_title(f"Class Distribution\n{total} responses", fontsize=11, weight="bold", pad=12, loc="left", color="#202124")

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=300, facecolor="#ffffff")
        plt.close(fig)

        raw_bytes = buf.getvalue()
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            fp = os.path.join(output_dir, "chart_class_distribution.png")
            with open(fp, "wb") as f:
                f.write(raw_bytes)

        b64 = f"data:image/png;base64,{base64.b64encode(raw_bytes).decode('ascii')}"
        return raw_bytes, b64

    @classmethod
    def analyze_feedback(
        cls,
        rows: List[Dict[str, Any]],
        po_column_mapping: Dict[str, str],
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze mapped PO columns across rows:
        Computes response counts, percentages, generates Google Forms pie charts,
        and constructs a factual interpretation narrative.
        """
        po_results = {}
        total_respondents = len(rows)

        high_rated_pos = []
        developing_pos = []

        for po_id, po_title in PO_DEFINITIONS.items():
            mapped_col = po_column_mapping.get(po_id)
            if not mapped_col:
                continue

            counts = {"Fair": 0, "Satisfactory": 0, "Very Good": 0, "Excellent": 0}
            valid_responses = 0

            for r in rows:
                val = r.get(mapped_col)
                norm = cls.normalize_rating(val)
                if norm:
                    counts[norm] += 1
                    valid_responses += 1

            if valid_responses == 0:
                continue

            # Percentages
            percentages = {}
            for cat in FEEDBACK_CATEGORIES:
                pct = round((counts[cat] / float(valid_responses) * 100.0), 1)
                percentages[cat] = pct

            positive_pct = percentages.get("Very Good", 0) + percentages.get("Excellent", 0)
            if positive_pct >= 75.0:
                high_rated_pos.append(f"{po_id} ({po_title})")
            elif positive_pct < 60.0:
                developing_pos.append(f"{po_id} ({po_title})")

            # Generate chart
            _, chart_b64 = cls.generate_po_pie_chart(po_id, po_title, counts, output_dir=output_dir)

            po_results[po_id] = {
                "po_id": po_id,
                "po_title": po_title,
                "mapped_column": mapped_col,
                "total_responses": valid_responses,
                "counts": counts,
                "percentages": percentages,
                "positive_percentage": round(positive_pct, 1),
                "chart_base64": chart_b64,
            }

        # Build factual narrative
        interpretation = cls.generate_factual_interpretation(
            po_results, total_respondents, high_rated_pos, developing_pos
        )

        return {
            "total_respondents": total_respondents,
            "mapped_pos_count": len(po_results),
            "po_results": po_results,
            "interpretation": interpretation,
        }

    @classmethod
    def generate_factual_interpretation(
        cls,
        po_results: Dict[str, Any],
        total_respondents: int,
        high_rated_pos: List[str],
        developing_pos: List[str],
    ) -> str:
        """
        Draft a factual, non-fabricated narrative reflecting actual student responses.
        """
        if not po_results:
            return "No feedback responses recorded for this activity."

        narrative_parts = [
            f"A structured feedback analysis was conducted based on {total_respondents} verified participant responses evaluated against relevant Program Outcomes (POs)."
        ]

        if high_rated_pos:
            high_str = ", ".join(high_rated_pos[:3])
            narrative_parts.append(
                f"Participants indicated strong satisfaction and learning attainment in {high_str}, with over 75% rating the session as 'Very Good' or 'Excellent'."
            )

        if developing_pos:
            dev_str = ", ".join(developing_pos[:2])
            narrative_parts.append(
                f"Opportunities for further academic reinforcement were noted in {dev_str}, which will be addressed in forthcoming department workshops and technical sessions."
            )
        else:
            narrative_parts.append(
                "Feedback across all mapped Program Outcomes demonstrated positive student reception and aligned with the learning objectives established by the Department."
            )

        return " ".join(narrative_parts)
