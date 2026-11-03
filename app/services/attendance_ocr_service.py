import os
import io
import re
import tempfile
import subprocess
import glob
import logging
from typing import List, Dict, Any, Tuple, Optional
import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Standard Department of Electronics & Communication Engineering (CUestIC)
# Cohort and Academic Class mapping
DEPARTMENT_CLASS_PREFIXES = {
    "2460": "4BTEC",
    "2462": "4BTELCS",
    "2360": "6BTEC",
    "2362": "6BTELCS",
    "2260": "8BTEC",
    "2262": "8BTELCS",
    "2560": "2BTEC",
    "2561": "2BTEC",
    "2562": "2BTELCS",
    "2660": "1BTEC",
    "2661": "1BTCS",
    "2662": "1BTELCS",
    "2663": "1BTELCS",
}


class AttendanceOCRService:
    """
    Automated attendance sheet processing and signature verification service.
    Extracts registration numbers, verifies signature presence in the designated 3rd/4th column,
    performs deduplication, and generates class-wise attendance distributions.
    """

    _ocr_engine = None

    @classmethod
    def get_ocr_engine(cls):
        """Lazy load RapidOCR engine once for high efficiency."""
        if cls._ocr_engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                cls._ocr_engine = RapidOCR()
            except Exception as e:
                logger.error("Failed to initialize RapidOCR engine: %s", e)
                raise
        return cls._ocr_engine

    @classmethod
    def extract_page_images(cls, file_bytes: bytes) -> List[np.ndarray]:
        """
        Convert file bytes (PDF or Image) into a list of BGR numpy image arrays.
        Multi-page PDFs are rendered into individual page images at 150 DPI.
        """
        if not file_bytes:
            return []

        # Check if PDF
        if file_bytes[:5] == b"%PDF-":
            images = []
            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_path = os.path.join(tmpdir, "attendance.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(file_bytes)

                prefix = os.path.join(tmpdir, "page")
                try:
                    subprocess.run(
                        ["pdftoppm", "-png", "-r", "150", pdf_path, prefix],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True,
                        timeout=45,
                    )
                    page_files = sorted(glob.glob(os.path.join(tmpdir, "page-*.png")))
                    for pf in page_files:
                        img = cv2.imread(pf)
                        if img is not None:
                            images.append(img)
                except Exception as err:
                    logger.warning("pdftoppm conversion failed: %s", err)
            if images:
                return images

        # Single image format
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            return [img]
        return []

    @classmethod
    def map_registration_to_class(cls, reg_no: str, member_directory: Optional[Dict[str, str]] = None) -> str:
        """
        Map registration number to academic class.
        1. Checks explicit member directory if provided.
        2. Checks department cohort mapping table.
        3. Defaults to 'Unmapped' to prevent incorrect inference.
        """
        clean_reg = str(reg_no).strip()
        if member_directory and clean_reg in member_directory:
            return member_directory[clean_reg]

        prefix4 = clean_reg[:4]
        if prefix4 in DEPARTMENT_CLASS_PREFIXES:
            return DEPARTMENT_CLASS_PREFIXES[prefix4]

        return "Unmapped"

    @classmethod
    def detect_signature_presence(
        cls,
        gray_img: np.ndarray,
        y0: int,
        y1: int,
        x0: int,
        x1: int
    ) -> Tuple[bool, str, float]:
        """
        Analyze the cropped signature cell.
        Returns: (has_signature: bool, confidence: str, dark_ratio: float)
        """
        h, w = gray_img.shape[:2]
        y0_clamped = max(0, min(h - 1, y0))
        y1_clamped = max(0, min(h, y1))
        x0_clamped = max(0, min(w - 1, x0))
        x1_clamped = max(0, min(w, x1))

        if y1_clamped <= y0_clamped or x1_clamped <= x0_clamped:
            return False, "Low", 0.0

        crop = gray_img[y0_clamped:y1_clamped, x0_clamped:x1_clamped]
        total_pixels = crop.size
        if total_pixels == 0:
            return False, "Low", 0.0

        # Otsu / thresholding to isolate pen strokes from paper
        # Paper is bright (>190), ink is dark (<160)
        dark_pixels = np.sum(crop < 160)
        dark_ratio = (dark_pixels / float(total_pixels)) * 100.0

        # Edge detection for pen stroke contours
        edges = cv2.Canny(crop, 50, 150)
        edge_pixels = np.sum(edges > 0)
        edge_ratio = (edge_pixels / float(total_pixels)) * 100.0

        # Decision rule:
        # Clear ink signature: dark_ratio > 3.0 or edge_ratio > 2.0
        # Clearly blank: dark_ratio < 0.8 and edge_ratio < 0.8
        # Uncertain / review: in between
        if dark_ratio >= 3.0 or edge_ratio >= 2.0:
            return True, "High", float(round(dark_ratio, 2))
        elif dark_ratio < 0.8 and edge_ratio < 0.8:
            return False, "High", float(round(dark_ratio, 2))
        else:
            # Uncertain / light pencil or faint mark
            has_sig = dark_ratio >= 1.5 or edge_ratio >= 1.2
            return bool(has_sig), "Low", float(round(dark_ratio, 2))

    @classmethod
    def process_attendance_file(
        cls,
        file_bytes: bytes,
        filename: str = "attendance_sheet",
        member_directory: Optional[Dict[str, str]] = None,
        existing_records: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Process attendance document (PDF or image).
        Extracts rows, registration numbers, verifies signatures, and aggregates class stats.
        """
        ocr = cls.get_ocr_engine()
        page_images = cls.extract_page_images(file_bytes)

        if not page_images:
            return {
                "success": False,
                "error": "Failed to extract or decode images from the provided file.",
                "records": [],
                "summary": {},
            }

        all_records: List[Dict[str, Any]] = []
        seen_reg_numbers = set()

        if existing_records:
            for r in existing_records:
                if r.get("status") == "Verified" and r.get("reg_no"):
                    seen_reg_numbers.add(r.get("reg_no"))

        total_pages = len(page_images)

        for page_idx, img in enumerate(page_images, start=1):
            h, w = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Perform OCR on page
            result, _ = ocr(img)
            if not result:
                continue

            # Step 1: Detect table columns (Signature column X boundaries)
            sig_box = None
            name_box = None
            reg_header_box = None

            for box, text, _ in result:
                t_lower = text.lower()
                if "sign" in t_lower:
                    sig_box = box
                elif "name" in t_lower:
                    name_box = box
                elif "reg" in t_lower:
                    reg_header_box = box

            if sig_box:
                xs = [pt[0] for pt in sig_box]
                sig_x0 = int(min(xs) - 15)
                sig_x1 = int(max(xs) + 40)
            elif name_box:
                # Signature column is immediately to the right of Name column
                name_xs = [pt[0] for pt in name_box]
                sig_x0 = int(max(name_xs) + 10)
                sig_x1 = int(min(w, sig_x0 + (w * 0.35)))
            else:
                # Standard right 28% of attendance sheet
                sig_x0 = int(w * 0.68)
                sig_x1 = int(w * 0.96)

            # Step 2: Extract candidate registration rows
            # Christ Univ pattern: 7 digits starting with 20-26, or general 6-8 digit numbers
            reg_candidates = []
            for box, text, score in result:
                text_clean = text.strip()
                # Check for 7-digit registration number
                match = re.search(r"\b(2[0-6]\d{5})\b", text_clean)
                if match:
                    reg_no = match.group(1)
                    ys = [pt[1] for pt in box]
                    y0, y1 = int(min(ys)), int(max(ys))
                    reg_candidates.append({
                        "reg_no": reg_no,
                        "y0": y0,
                        "y1": y1,
                        "score": float(score) if score is not None else 0.85,
                        "box": box,
                    })

            # Sort candidate rows top-to-bottom
            reg_candidates.sort(key=lambda item: item["y0"])

            # Step 3: Analyze each row for signature presence and student details
            for cand in reg_candidates:
                reg_no = cand["reg_no"]
                y0, y1 = cand["y0"], cand["y1"]
                row_h = y1 - y0

                # Expand vertical signature bounding box slightly for natural pen strokes
                sig_y0 = max(0, y0 - int(row_h * 0.15))
                sig_y1 = min(h, y1 + int(row_h * 0.25))

                has_sig, conf, dark_ratio = cls.detect_signature_presence(
                    gray, sig_y0, sig_y1, sig_x0, sig_x1
                )

                # Find associated student name in same horizontal row
                student_name = ""
                for box, text, _ in result:
                    t_clean = text.strip()
                    if t_clean == reg_no or "register" in t_clean.lower() or "signature" in t_clean.lower():
                        continue
                    b_ys = [pt[1] for pt in box]
                    b_y_mid = (min(b_ys) + max(b_ys)) / 2.0
                    if y0 - (row_h * 0.4) <= b_y_mid <= y1 + (row_h * 0.4):
                        # Verify this text is in the name column zone (between reg and sig)
                        b_xs = [pt[0] for pt in box]
                        b_x_min = min(b_xs)
                        if b_x_min > (w * 0.25) and b_x_min < sig_x0:
                            student_name = t_clean
                            break

                mapped_class = cls.map_registration_to_class(reg_no, member_directory)

                # Check duplicate status
                is_duplicate = reg_no in seen_reg_numbers
                if is_duplicate:
                    status = "Duplicate"
                elif has_sig and conf == "High":
                    status = "Verified"
                    seen_reg_numbers.add(reg_no)
                elif not has_sig and conf == "High":
                    status = "Excluded"
                else:
                    status = "Review Required"

                record = {
                    "reg_no": reg_no,
                    "student_name": student_name,
                    "page_number": page_idx,
                    "signature_detected": has_sig,
                    "confidence": conf,
                    "ink_density": dark_ratio,
                    "status": status,
                    "mapped_class": mapped_class,
                    "is_duplicate": is_duplicate,
                    "y_coord": y0,
                }
                all_records.append(record)

        # Compute summary metrics
        summary = cls.compute_attendance_summary(all_records)

        return {
            "success": True,
            "filename": filename,
            "total_pages": total_pages,
            "records": all_records,
            "summary": summary,
        }

    @classmethod
    def compute_attendance_summary(cls, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate summary metrics and class distribution from extracted attendance records.
        Attendance verification rule:
        A participant is counted as attended ONLY when valid registration number is extracted,
        not duplicate, and signature is detected (status == 'Verified').
        """
        total_rows = len(records)
        extracted_reg_nos = [r["reg_no"] for r in records if r.get("reg_no")]
        total_extracted = len(extracted_reg_nos)

        with_signatures = sum(1 for r in records if r.get("signature_detected") is True)
        verified_records = [r for r in records if r.get("status") == "Verified"]
        verified_unique = len(verified_records)

        duplicates = sum(1 for r in records if r.get("status") == "Duplicate" or r.get("is_duplicate"))
        excluded = sum(1 for r in records if r.get("status") == "Excluded")
        review_required = sum(1 for r in records if r.get("status") == "Review Required")

        # Class distribution for verified participants
        class_dist: Dict[str, int] = {}
        for r in verified_records:
            c = r.get("mapped_class") or "Unmapped"
            class_dist[c] = class_dist.get(c, 0) + 1

        # Calculate percentages
        class_distribution_list = []
        for c_name, count in sorted(class_dist.items(), key=lambda x: x[1], reverse=True):
            pct = round((count / float(verified_unique) * 100.0), 1) if verified_unique > 0 else 0.0
            class_distribution_list.append({
                "class_name": c_name,
                "count": count,
                "percentage": pct,
            })

        return {
            "total_rows_detected": total_rows,
            "total_reg_numbers_extracted": total_extracted,
            "total_records_with_signatures": with_signatures,
            "total_verified_unique": verified_unique,
            "duplicate_records": duplicates,
            "excluded_records": excluded,
            "review_required_records": review_required,
            "class_distribution": class_distribution_list,
        }
