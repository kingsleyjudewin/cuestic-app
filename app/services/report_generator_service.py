import os
import io
import base64
import logging
import subprocess
import tempfile
import glob
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_BREAK, WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.text.paragraph import Paragraph
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

TEMPLATE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "templates", "template_cuestic_document.docx")
)

# Standard ABET/NBA 12 Impact Questions for Activity Reports
DEFAULT_IMPACT_QUESTIONS = [
    {"q": "1. How effectively did the activity address its stated objectives?", "a": "The activity successfully addressed its core objectives by providing structured technical exposure, experiential problem-solving opportunities, and peer collaboration for participating engineering students."},
    {"q": "2. How many verified participants attended the activity?", "a": "{verified_count} verified unique participants attended the activity with recorded signatures."},
    {"q": "3. Which academic classes were represented?", "a": "Participation was recorded across academic cohorts including {class_list}."},
    {"q": "4. Did the activity provide exposure to the intended technical subject?", "a": "Yes, participants engaged with domain-specific engineering principles, structured problem statements, and real-time execution scenarios."},
    {"q": "5. Did the activity provide opportunities for knowledge exchange?", "a": "Yes, interactive discussions and group challenges facilitated collaborative knowledge transfer between participants and coordinators."},
    {"q": "6. Did the activity encourage student engagement?", "a": "High engagement levels were observed throughout the session with active participant questions and competitive execution."},
    {"q": "7. Did the activity support practical or research-oriented learning?", "a": "Yes, the activity emphasized analytical thinking, deductive reasoning, and hands-on application rather than passive theoretical instruction."},
    {"q": "8. Did the activity facilitate interaction with speakers or experts?", "a": "Organizers, faculty coordinators, and student leads actively mentored teams during the session."},
    {"q": "9. Did the activity encourage interdisciplinary collaboration?", "a": "The activity fostered cross-sectional teamwork among students from Electronics and Communication Engineering and associated cohorts."},
    {"q": "10. Did the activity provide insights into relevant industry or research practices?", "a": "The problem statements reflected industry methodologies requiring agile problem solving, communication, and systematic verification."},
    {"q": "11. What key outcomes were documented during the activity?", "a": "Documented outcomes include verified participant completion, peer interaction, and positive attainment of relevant engineering program outcomes."},
    {"q": "12. What follow-up opportunities or improvements were identified?", "a": "Recommended follow-ups include organizing advanced continuation modules and expanding time allocations for complex analytical challenges."},
]


def prepare_image_for_docx(
    img_data: bytes,
    max_width_in: float = 6.0,
    max_height_in: float = 8.0,
) -> Optional[Tuple[io.BytesIO, float, float]]:
    """
    Process, sanitize, and proportionally scale an image for Microsoft Word (.docx).
    1. Handles alpha channels by compositing onto a crisp white background (no white/black line artifacts).
    2. Respects EXIF rotation orientation.
    3. Calculates aspect-ratio constrained width and height in inches so tall images
       never exceed page boundaries or get sliced across margins with white lines.
    4. Re-encodes as clean, optimized JPEG.
    Returns (BytesIO_buffer, target_width_inches, target_height_inches) or None.
    """
    if not img_data:
        return None

    try:
        im = Image.open(io.BytesIO(img_data))
        # Handle EXIF orientation
        try:
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass

        # Handle alpha channel / transparency: composite onto clean white canvas
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            if im.mode == "P":
                im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            mask = im.split()[-1] if im.mode in ("RGBA", "LA") else None
            bg.paste(im, mask=mask)
            im = bg
        elif im.mode != "RGB":
            im = im.convert("RGB")

        orig_w, orig_h = im.size
        if orig_w <= 0 or orig_h <= 0:
            return None

        aspect = orig_w / float(orig_h)

        # Scale proportionally to fit within max_width_in and max_height_in
        target_w = max_width_in
        target_h = target_w / aspect

        if target_h > max_height_in:
            target_h = max_height_in
            target_w = target_h * aspect

        # Cap max pixel dimension to 2400 for speed and small docx file size
        max_px = 2400
        if orig_w > max_px or orig_h > max_px:
            im.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=92, optimize=True)
        buf.seek(0)
        return buf, round(target_w, 2), round(target_h, 2)
    except Exception as e:
        logger.warning("Error preparing image for docx: %s", e)
        return None


def extract_images_from_data(raw_data: bytes) -> List[bytes]:
    """
    Given raw bytes of an image or PDF, return a list of image byte buffers.
    If the data is a PDF, renders each page as a PNG using pdftoppm.
    Otherwise returns [raw_data].
    """
    if not raw_data:
        return []

    # Check if PDF
    if raw_data[:5] == b"%PDF-":
        images = []
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "input.pdf")
            with open(pdf_path, "wb") as f:
                f.write(raw_data)

            prefix = os.path.join(tmpdir, "page")
            try:
                subprocess.run(
                    ["pdftoppm", "-png", "-r", "150", pdf_path, prefix],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=30,
                )
                page_files = sorted(glob.glob(os.path.join(tmpdir, "page-*.png")))
                for pf in page_files:
                    with open(pf, "rb") as pf_f:
                        images.append(pf_f.read())
            except Exception as pdf_err:
                logger.warning("Could not convert PDF to images via pdftoppm: %s", pdf_err)
        if images:
            return images

    return [raw_data]


def _apply_table_borders(table):
    """Apply clean borders to a table via OpenXML tblBorders."""
    tblPr = table._element.xpath('w:tblPr')
    if tblPr:
        borders = parse_xml(
            f'<w:tblBorders {nsdecls("w")}>\n'
            f'  <w:top w:val="single" w:sz="6" w:space="0" w:color="B0B0B0"/>\n'
            f'  <w:left w:val="single" w:sz="6" w:space="0" w:color="B0B0B0"/>\n'
            f'  <w:bottom w:val="single" w:sz="6" w:space="0" w:color="B0B0B0"/>\n'
            f'  <w:right w:val="single" w:sz="6" w:space="0" w:color="B0B0B0"/>\n'
            f'  <w:insideH w:val="single" w:sz="4" w:space="0" w:color="D0D0D0"/>\n'
            f'  <w:insideV w:val="single" w:sz="4" w:space="0" w:color="D0D0D0"/>\n'
            f'</w:tblBorders>'
        )
        tblPr[0].append(borders)


def _set_cell_text(
    cell,
    text: str,
    bold: bool = False,
    font_name: str = "Times New Roman",
    font_size_pt: int = 12,
    line_spacing: float = 1.15,
    italic: bool = False,
):
    """Set cell text with explicit font family, size, line spacing, preserving paragraph formatting."""
    cell.text = ""
    clean_text = (text or "").strip()
    if not clean_text:
        return

    paragraphs = [p.strip() for p in clean_text.split("\n") if p.strip()] if "\n" in clean_text else [clean_text]
    if not paragraphs:
        paragraphs = [clean_text]

    for idx, p_text in enumerate(paragraphs):
        p = cell.paragraphs[0] if idx == 0 else cell.add_paragraph()
        try:
            p.style = "normal1"
        except Exception:
            pass
        p.paragraph_format.line_spacing = line_spacing
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(p_text)
        run.font.name = font_name
        run.font.size = Pt(font_size_pt)
        run.font.bold = bold
        run.font.italic = italic


def _add_styled_paragraph(
    doc,
    text: str,
    bold: bool = False,
    italic: bool = False,
    font_size_pt: int = 12,
    insert_before_p=None,
    color_rgb=None,
    space_after_pt: int = 6,
):
    """Add or insert a styled paragraph in Times New Roman."""
    if insert_before_p is not None:
        p = insert_before_p.insert_paragraph_before()
    else:
        p = doc.add_paragraph()
    try:
        p.style = "normal1"
    except Exception:
        pass
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(space_after_pt)
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(font_size_pt)
    run.font.bold = bold
    run.font.italic = italic
    if color_rgb:
        run.font.color.rgb = color_rgb
    return p


class ReportGeneratorService:
    """
    Generates Microsoft Word (.docx) Activity Reports based strictly on the official
    template_cuestic_document.docx file.
    """

    @classmethod
    def get_template_path(cls) -> str:
        """Return verified path to master CUestIC docx template."""
        if os.path.exists(TEMPLATE_PATH):
            return TEMPLATE_PATH
        fallback = "/home/kingsley-judewin/Documents/template cuestic document.docx"
        if os.path.exists(fallback):
            return fallback
        raise FileNotFoundError(f"Master template file was not found at '{TEMPLATE_PATH}' or '{fallback}'.")

    @classmethod
    def generate_report_docx(
        cls,
        report_data: dict,
        output_filepath: str,
        image_resolver=None,
    ) -> str:
        """
        Populate the official CUestIC template with report_data and save to output_filepath.
        image_resolver: callable(storage_path_or_filename) -> bytes
        """
        template_file = cls.get_template_path()
        doc = docx.Document(template_file)

        if image_resolver is None:
            def _fallback_image_resolver(ref):
                if not ref:
                    return None
                if isinstance(ref, (bytes, bytearray)):
                    return bytes(ref)
                if isinstance(ref, str):
                    clean_ref = ref.strip()
                    if clean_ref.startswith("data:") or (len(clean_ref) > 100 and "," in clean_ref[:100]):
                        b64_part = clean_ref.split(",", 1)[1] if "," in clean_ref else clean_ref
                        return base64.b64decode("".join(b64_part.split()))
                    elif len(clean_ref) > 300 and not os.path.exists(clean_ref):
                        try:
                            return base64.b64decode("".join(clean_ref.split()))
                        except Exception:
                            pass
                    if os.path.exists(clean_ref):
                        with open(clean_ref, "rb") as f:
                            return f.read()
                return None
            image_resolver = _fallback_image_resolver

        # -------------------------------------------------------------
        # Section 1 — General Information (Table 0)
        # -------------------------------------------------------------
        gen_info = (
            report_data.get("general_information")
            or report_data.get("general_info")
            or report_data
            or {}
        )

        type_of_activity = (
            gen_info.get("type_of_activity")
            or report_data.get("type_of_activity")
            or "Department Club Activity"
        )
        title_of_activity = (
            gen_info.get("title_of_activity")
            or report_data.get("title_of_activity")
            or report_data.get("title")
            or "Activity Report"
        )
        date_str = (
            gen_info.get("date")
            or gen_info.get("dates")
            or gen_info.get("date_of_activity")
            or report_data.get("date")
            or ""
        )
        time_str = (
            gen_info.get("time")
            or gen_info.get("timings")
            or gen_info.get("duration")
            or report_data.get("time")
            or ""
        )
        venue_str = (
            gen_info.get("venue")
            or gen_info.get("location")
            or report_data.get("venue")
            or ""
        )
        collaborators_str = (
            gen_info.get("collaborators")
            or report_data.get("collaborators")
            or ""
        )

        if len(doc.tables) > 0:
            t0 = doc.tables[0]
            if len(t0.rows) >= 5:
                _set_cell_text(t0.rows[0].cells[1], type_of_activity)
                _set_cell_text(t0.rows[1].cells[1], title_of_activity, bold=True)
                dt_str = f"{date_str}  |  {time_str}".strip(" |") if time_str else date_str
                _set_cell_text(t0.rows[2].cells[1], dt_str)
                _set_cell_text(t0.rows[3].cells[1], venue_str)
                _set_cell_text(t0.rows[4].cells[1], collaborators_str)

        # -------------------------------------------------------------
        # Section 2 — Speaker Details (Table 1)
        # -------------------------------------------------------------
        speakers = report_data.get("speakers") or []
        valid_speakers = [s for s in speakers if isinstance(s, dict) and s.get("name") and s.get("name").strip()]
        if not valid_speakers:
            speaker_detail = report_data.get("speaker_detail") or report_data.get("speaker_details")
            if isinstance(speaker_detail, dict) and speaker_detail.get("name"):
                valid_speakers = [speaker_detail]
            elif isinstance(speaker_detail, str) and speaker_detail.strip():
                valid_speakers = [{"name": speaker_detail.strip(), "title": "", "organization": "", "presentation_title": title_of_activity}]
            else:
                valid_speakers = [{
                    "name": "Internal Faculty & Student Coordinators",
                    "title": "Coordinators",
                    "organization": "Department of Electronics and Communication Engineering, CHRIST (Deemed to be University)",
                    "presentation_title": title_of_activity,
                }]

        if len(doc.tables) > 1 and len(doc.tables[1].rows) >= 4:
            t1 = doc.tables[1]
            spk1 = valid_speakers[0]
            spk1_title = spk1.get("title") or spk1.get("position") or spk1.get("designation") or ""
            spk1_org = spk1.get("organization") or spk1.get("institution") or ""
            spk1_pres = spk1.get("presentation_title") or spk1.get("topic") or spk1.get("title_of_presentation") or title_of_activity

            _set_cell_text(t1.rows[0].cells[1], spk1.get("name", ""))
            _set_cell_text(t1.rows[1].cells[1], spk1_title)
            _set_cell_text(t1.rows[2].cells[1], spk1_org)
            _set_cell_text(t1.rows[3].cells[1], spk1_pres)

            labels = ["Name", "Title/Position", "Organization", "Title of Presentation"]
            for spk in valid_speakers[1:]:
                name_val = spk.get("name", "")
                title_val = spk.get("title") or spk.get("position") or spk.get("designation") or ""
                org_val = spk.get("organization") or spk.get("institution") or ""
                pres_val = spk.get("presentation_title") or spk.get("topic") or spk.get("title_of_presentation") or title_of_activity

                for lbl, val in zip(labels, [name_val, title_val, org_val, pres_val]):
                    new_row = t1.add_row()
                    _set_cell_text(new_row.cells[0], lbl, bold=True)
                    _set_cell_text(new_row.cells[1], val)

        # -------------------------------------------------------------
        # Section 3 — Participants Profile (Tables 2, 3, 4, 5)
        # Enhanced with verified attendance count and class representation
        # -------------------------------------------------------------
        participants = (
            report_data.get("participants")
            or report_data.get("participants_profile")
            or {}
        )
        type_of_participants = (
            participants.get("type_of_participants")
            or report_data.get("type_of_participants")
            or "UG & PG Students of CHRIST (Deemed to be University)"
        )
        highlights = (
            participants.get("highlights")
            or participants.get("highlights_of_activity")
            or report_data.get("highlights")
            or ""
        )
        summary = (
            participants.get("summary")
            or participants.get("summary_of_activities")
            or report_data.get("summary")
            or report_data.get("description")
            or ""
        )
        key_takeaways = (
            participants.get("key_takeaways")
            or report_data.get("key_takeaways")
            or ""
        )

        # Retrieve attendance summary
        att_summary = report_data.get("attendance_summary") or {}
        verified_count = (
            att_summary.get("total_verified_unique")
            or report_data.get("verified_attendance_count")
        )
        class_dist = att_summary.get("class_distribution") or []

        participant_text = type_of_participants
        if verified_count:
            participant_text += f"\nTotal Verified Attendees: {verified_count}"
        if class_dist:
            dist_str = ", ".join([f"{item['class_name']} ({item['count']})" for item in class_dist])
            participant_text += f"\nClass Representation: {dist_str}"

        # Table 2: Type of Participants
        if len(doc.tables) > 2 and len(doc.tables[2].rows) >= 1:
            _set_cell_text(doc.tables[2].rows[0].cells[1], participant_text)

        # Table 3: Highlights of the Activity
        if len(doc.tables) > 3 and len(doc.tables[3].rows) >= 1:
            _set_cell_text(doc.tables[3].rows[0].cells[1], highlights)

        # Table 4: Summary of the Activities (1x1 container table)
        if len(doc.tables) > 4 and len(doc.tables[4].rows) >= 1:
            _set_cell_text(doc.tables[4].rows[0].cells[0], summary)

        # Table 5: Key Takeaways
        if len(doc.tables) > 5 and len(doc.tables[5].rows) >= 1:
            _set_cell_text(doc.tables[5].rows[0].cells[1], key_takeaways)

        # -------------------------------------------------------------
        # Section 4 — Report Prepared By (Table 6)
        # -------------------------------------------------------------
        organiser = (
            report_data.get("organiser")
            or report_data.get("report_prepared_by")
            or {}
        )
        organiser_name = (
            organiser.get("name")
            or organiser.get("organiser_name")
            or report_data.get("created_by_name")
            or "Documentation Coordinator"
        )
        designation = (
            organiser.get("designation")
            or organiser.get("title")
            or "Documentation Lead, CUestIC"
        )
        sig_text = organiser.get("signature") or organiser.get("signature_text") or "Signed"

        if len(doc.tables) > 6 and len(doc.tables[6].rows) >= 3:
            t6 = doc.tables[6]
            _set_cell_text(t6.rows[0].cells[1], organiser_name)
            _set_cell_text(t6.rows[1].cells[1], designation)

            sig_cell = t6.rows[2].cells[1]
            sig_cell.text = ""
            sig_image_bytes = None
            if image_resolver and organiser.get("signature_image_path"):
                try:
                    sig_image_bytes = image_resolver(organiser["signature_image_path"])
                except Exception as e:
                    logger.warning("Could not resolve signature image: %s", e)

            if sig_image_bytes:
                try:
                    p = sig_cell.paragraphs[0]
                    p.add_run().add_picture(io.BytesIO(sig_image_bytes), width=Inches(1.8))
                except Exception:
                    _set_cell_text(sig_cell, sig_text)
            else:
                _set_cell_text(sig_cell, sig_text)

        # -------------------------------------------------------------
        # Section 5 — Speaker Profile
        # -------------------------------------------------------------
        speaker_profile = (
            report_data.get("speaker_profile")
            or report_data.get("speaker_profiles")
            or ""
        )
        if not speaker_profile and valid_speakers and valid_speakers[0].get("name") != "Internal Faculty & Student Coordinators":
            spk_obj = valid_speakers[0]
            speaker_profile = f"{spk_obj.get('name')}, {spk_obj.get('title', '')} at {spk_obj.get('organization', '')}."

        spk_heading_p = None
        for p in doc.paragraphs:
            if "Speaker Profile:" in p.text:
                spk_heading_p = p
                break

        if spk_heading_p:
            next_elem = spk_heading_p._element.getnext()
            if next_elem is not None:
                new_p_elem = OxmlElement("w:p")
                next_elem.addprevious(new_p_elem)
                p_bio = Paragraph(new_p_elem, doc)
            else:
                p_bio = doc.add_paragraph()

            p_bio.paragraph_format.line_spacing = 1.15
            p_bio.paragraph_format.space_after = Pt(8)
            content_to_insert = (
                speaker_profile.strip()
                if speaker_profile and speaker_profile.strip()
                else "Event organized and coordinated by the Department of Electronics and Communication Engineering, CUestIC, CHRIST (Deemed to be University)."
            )
            run = p_bio.add_run(content_to_insert)
            run.font.name = "Times New Roman"
            run.font.size = Pt(12)
            if not speaker_profile or not speaker_profile.strip():
                run.font.italic = True

        # -------------------------------------------------------------
        # Section 6 — Annexures: Photos, Attendance, Poster, E-Certificate, Impact, Feedback
        # -------------------------------------------------------------
        annexures = report_data.get("annexures") or {}

        # Check user attachments
        user_feedback_text = (report_data.get("feedback_analysis") or "").strip()
        po_results = report_data.get("po_results") or (report_data.get("feedback_data") or {}).get("po_results") or {}
        user_has_feedback = bool(user_feedback_text or po_results)

        cert_ref = (
            annexures.get("certificate_base64")
            or annexures.get("certificate")
            or annexures.get("certificates")
            or annexures.get("sample_certificate")
            or report_data.get("certificate")
        )
        user_has_certificate = bool(cert_ref)

        # 1. Purge template dummy drawings (rId2 to rId16), placeholder text, and old semiconductor paragraphs
        to_remove = []
        in_feedback_block = False
        in_certificate_block = False

        for p in list(doc.paragraphs):
            txt = p.text.strip()

            if "Feedback Analysis:" in txt:
                in_feedback_block = True
                continue

            if "Impact Analysis:" in txt:
                in_feedback_block = False

            if in_feedback_block:
                to_remove.append(p)
                continue

            if "Sample E-Certificate:" in txt:
                in_certificate_block = True
                if not user_has_certificate:
                    to_remove.append(p)
                continue

            if in_certificate_block:
                if "Feedback Analysis:" in txt or "Impact Analysis:" in txt:
                    in_certificate_block = False
                else:
                    if not user_has_certificate:
                        to_remove.append(p)
                        continue

            if "poster image should be uploade" in txt:
                to_remove.append(p)
                continue

            # Remove old template blips (rId2: poster, rId3: cert, rId4-16: charts)
            blip_rids = p._element.xpath(".//a:blip/@r:embed")
            if blip_rids and any(rid in ("rId2", "rId3", "rId4", "rId5", "rId6", "rId7", "rId8", "rId9", "rId10", "rId11", "rId12", "rId13", "rId14", "rId15", "rId16") for rid in blip_rids):
                to_remove.append(p)

        for p in to_remove:
            try:
                p._element.getparent().remove(p._element)
            except Exception:
                pass

        # Clean consecutive blank paragraphs to prevent phantom blank pages
        last_was_empty = False
        for p in list(doc.paragraphs):
            if not p.text.strip() and not p._element.xpath(".//w:drawing"):
                if last_was_empty:
                    try:
                        p._element.getparent().remove(p._element)
                    except Exception:
                        pass
                else:
                    last_was_empty = True
            else:
                last_was_empty = False

        # Scan for active markers in cleaned document
        photos_marker_p = None
        attendance_marker_p = None
        poster_marker_p = None
        certificate_marker_p = None
        feedback_marker_p = None
        impact_marker_p = None
        impact_body_p1 = None
        impact_body_p2 = None

        for idx, p in enumerate(doc.paragraphs):
            txt = p.text.strip()
            if "Photos of Activity" in txt:
                photos_marker_p = p
            elif "Attendance list of participants" in txt:
                attendance_marker_p = p
            elif txt == "Poster:":
                poster_marker_p = p
            elif "Sample E-Certificate:" in txt:
                certificate_marker_p = p
            elif "Impact Analysis:" in txt:
                impact_marker_p = p
                for scan_p in doc.paragraphs[idx:min(idx + 5, len(doc.paragraphs))]:
                    if "technical talk significantly enhanced" in scan_p.text:
                        impact_body_p1 = scan_p
                    elif "Furthermore, the talk inspired" in scan_p.text:
                        impact_body_p2 = scan_p
            elif "Feedback Analysis:" in txt:
                feedback_marker_p = p

        # -------------------------------------------------------------
        # 1. Activity Photos
        # -------------------------------------------------------------
        activity_photos = annexures.get("photos_base64") or annexures.get("photos") or []
        if photos_marker_p:
            photos_marker_p.text = "Photos of Activity:"
            inserted_photos = 0
            if activity_photos and image_resolver:
                next_el = photos_marker_p._element.getnext()
                for photo_ref in activity_photos:
                    try:
                        raw_data = image_resolver(photo_ref)
                        if not raw_data:
                            continue
                        all_img_data = extract_images_from_data(raw_data)
                        for img_data in all_img_data:
                            prepared = prepare_image_for_docx(img_data, max_width_in=5.5, max_height_in=6.5)
                            if prepared:
                                buf, w_in, h_in = prepared
                                new_el = OxmlElement("w:p")
                                if next_el is not None:
                                    next_el.addprevious(new_el)
                                else:
                                    doc._body._body.append(new_el)
                                p_img = Paragraph(new_el, doc)
                                p_img.paragraph_format.space_before = Pt(4)
                                p_img.paragraph_format.space_after = Pt(12)
                                p_img.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                                run = p_img.add_run()
                                run.add_picture(buf, width=Inches(w_in), height=Inches(h_in))
                                inserted_photos += 1
                    except Exception as e:
                        logger.warning("Could not insert activity photo: %s", e)

            if inserted_photos == 0:
                photos_marker_p.text = "Photos of Activity: Documented and archived in the Department Event Repository."

        # -------------------------------------------------------------
        # 2. Attendance List & Summary Table
        # -------------------------------------------------------------
        attendance_pages = (
            annexures.get("attendance_sheets_base64")
            or annexures.get("attendance_pages_base64")
            or annexures.get("attendance_sheets")
            or annexures.get("attendance_pages")
            or []
        )

        if attendance_marker_p:
            attendance_marker_p.text = "Attendance list of participants:"
            inserted_att = 0

            # If class distribution exists, add a neat class breakdown summary table above images
            if class_dist:
                tbl_el = doc.add_table(rows=1 + len(class_dist), cols=3)
                _apply_table_borders(tbl_el)
                tbl_el.alignment = WD_TABLE_ALIGNMENT.CENTER
                # Set headers
                _set_cell_text(tbl_el.rows[0].cells[0], "Academic Class", bold=True, font_size_pt=10)
                _set_cell_text(tbl_el.rows[0].cells[1], "Verified Attendees", bold=True, font_size_pt=10)
                _set_cell_text(tbl_el.rows[0].cells[2], "Representation (%)", bold=True, font_size_pt=10)

                for row_idx, item in enumerate(class_dist, start=1):
                    _set_cell_text(tbl_el.rows[row_idx].cells[0], str(item.get("class_name", "")), font_size_pt=10)
                    _set_cell_text(tbl_el.rows[row_idx].cells[1], str(item.get("count", "")), font_size_pt=10)
                    _set_cell_text(tbl_el.rows[row_idx].cells[2], f"{item.get('percentage', 0.0)}%", font_size_pt=10)

                # Move table element immediately after attendance marker
                next_el = attendance_marker_p._element.getnext()
                if next_el is not None:
                    next_el.addprevious(tbl_el._element)

            if attendance_pages and image_resolver:
                prepared_sheets = []
                for att_ref in attendance_pages:
                    try:
                        raw_data = image_resolver(att_ref)
                        if not raw_data:
                            continue
                        all_img_data = extract_images_from_data(raw_data)
                        for img_data in all_img_data:
                            prep = prepare_image_for_docx(img_data, max_width_in=6.0, max_height_in=8.0)
                            if prep:
                                prepared_sheets.append(prep)
                    except Exception as e:
                        logger.warning("Could not resolve attendance sheet %s: %s", att_ref, e)

                total_sheets = len(prepared_sheets)
                if total_sheets > 0:
                    next_el = attendance_marker_p._element.getnext()
                    for idx, (buf, w_in, h_in) in enumerate(prepared_sheets):
                        try:
                            if total_sheets > 1:
                                caption_el = OxmlElement("w:p")
                                if next_el is not None:
                                    next_el.addprevious(caption_el)
                                else:
                                    doc._body._body.append(caption_el)
                                p_cap = Paragraph(caption_el, doc)
                                p_cap.paragraph_format.space_before = Pt(6)
                                p_cap.paragraph_format.space_after = Pt(4)
                                p_cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                                run_cap = p_cap.add_run(f"Attendance Sheet — Page {idx + 1} of {total_sheets}")
                                run_cap.font.name = "Times New Roman"
                                run_cap.font.size = Pt(11)
                                run_cap.font.bold = True
                                run_cap.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

                            img_el = OxmlElement("w:p")
                            if next_el is not None:
                                next_el.addprevious(img_el)
                            else:
                                doc._body._body.append(img_el)
                            p_att = Paragraph(img_el, doc)
                            p_att.paragraph_format.space_before = Pt(2)
                            p_att.paragraph_format.space_after = Pt(12)
                            p_att.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            run = p_att.add_run()
                            run.add_picture(buf, width=Inches(w_in), height=Inches(h_in))

                            if idx < total_sheets - 1:
                                p_att.add_run().add_break(WD_BREAK.PAGE)
                            inserted_att += 1
                        except Exception as e:
                            logger.warning("Could not render attendance sheet page %d: %s", idx + 1, e)

            if inserted_att == 0 and not class_dist:
                attendance_marker_p.text = "Attendance list of participants: Verified and preserved in departmental physical records."

        # -------------------------------------------------------------
        # 3. Poster Image
        # -------------------------------------------------------------
        poster_ref = (
            annexures.get("poster_base64")
            or annexures.get("poster")
            or annexures.get("poster_path")
            or report_data.get("poster")
            or report_data.get("poster_base64")
        )

        if poster_marker_p:
            poster_marker_p.text = "Poster:"
            inserted_poster = False
            if poster_ref and image_resolver:
                try:
                    raw_data = image_resolver(poster_ref)
                    if raw_data:
                        all_img_data = extract_images_from_data(raw_data)
                        if all_img_data:
                            prepared = prepare_image_for_docx(all_img_data[0], max_width_in=5.5, max_height_in=7.5)
                            if prepared:
                                buf, w_in, h_in = prepared
                                next_el = poster_marker_p._element.getnext()
                                new_el = OxmlElement("w:p")
                                if next_el is not None:
                                    next_el.addprevious(new_el)
                                else:
                                    doc._body._body.append(new_el)
                                p_poster = Paragraph(new_el, doc)
                                p_poster.paragraph_format.space_before = Pt(4)
                                p_poster.paragraph_format.space_after = Pt(12)
                                p_poster.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                                run = p_poster.add_run()
                                run.add_picture(buf, width=Inches(w_in), height=Inches(h_in))
                                inserted_poster = True
                except Exception as e:
                    logger.warning("Could not insert poster image: %s", e)

            if not inserted_poster:
                poster_marker_p.text = "Poster: Archived with Department Media Team."

        # -------------------------------------------------------------
        # 4. Sample E-Certificate (BEFORE Impact Analysis!)
        # -------------------------------------------------------------
        if certificate_marker_p and user_has_certificate:
            certificate_marker_p.text = "Sample E-Certificate:"
            inserted_cert = False
            if image_resolver:
                try:
                    raw_data = image_resolver(cert_ref)
                    if raw_data:
                        all_img_data = extract_images_from_data(raw_data)
                        if all_img_data:
                            prepared = prepare_image_for_docx(all_img_data[0], max_width_in=6.0, max_height_in=7.5)
                            if prepared:
                                buf, w_in, h_in = prepared
                                next_el = certificate_marker_p._element.getnext()
                                new_el = OxmlElement("w:p")
                                if next_el is not None:
                                    next_el.addprevious(new_el)
                                else:
                                    doc._body._body.append(new_el)
                                p_cert = Paragraph(new_el, doc)
                                p_cert.paragraph_format.space_before = Pt(4)
                                p_cert.paragraph_format.space_after = Pt(6)
                                p_cert.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                                run = p_cert.add_run()
                                run.add_picture(buf, width=Inches(w_in), height=Inches(h_in))
                                inserted_cert = True

                                # Optional certificate caption
                                cert_cat = annexures.get("certificate_category") or "Participation"
                                cert_count = annexures.get("certificates_issued") or verified_count or ""
                                cert_caption = f"Sample E-Certificate issued to participants. Category: {cert_cat}"
                                if cert_count:
                                    cert_caption += f" | Total Certificates Issued: {cert_count}"

                                cap_el = OxmlElement("w:p")
                                if next_el is not None:
                                    next_el.addprevious(cap_el)
                                else:
                                    doc._body._body.append(cap_el)
                                p_cap = Paragraph(cap_el, doc)
                                p_cap.paragraph_format.space_before = Pt(2)
                                p_cap.paragraph_format.space_after = Pt(12)
                                p_cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                                r_cap = p_cap.add_run(cert_caption)
                                r_cap.font.name = "Times New Roman"
                                r_cap.font.size = Pt(10)
                                r_cap.font.italic = True
                                r_cap.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
                except Exception as e:
                    logger.warning("Could not insert certificate image: %s", e)

            if not inserted_cert:
                certificate_marker_p.text = "Sample E-Certificate: Distributed via institutional portal upon session completion."

        # -------------------------------------------------------------
        # 5. Impact Analysis (Removed per user request)
        # -------------------------------------------------------------
        if impact_marker_p:
            try:
                impact_marker_p._element.getparent().remove(impact_marker_p._element)
            except Exception:
                pass
        if impact_body_p1:
            try:
                impact_body_p1._element.getparent().remove(impact_body_p1._element)
            except Exception:
                pass
        if impact_body_p2:
            try:
                impact_body_p2._element.getparent().remove(impact_body_p2._element)
            except Exception:
                pass

        # -------------------------------------------------------------
        # 6. Feedback Analysis (PO1-PO12 Pie Charts Only)
        # -------------------------------------------------------------
        if user_has_feedback and feedback_marker_p:
            feedback_marker_p.text = "Feedback Analysis:"
            next_el = feedback_marker_p._element.getnext()

            # Insert PO Question Headings and Charts (only question + pie chart, nothing below)
            if po_results and image_resolver:
                for po_id, po_data in po_results.items():
                    chart_ref = po_data.get("chart_base64")
                    po_title = po_data.get("po_title") or po_id
                    po_q = po_data.get("po_question") or po_data.get("mapped_column") or ""

                    # 1. Insert Question Heading
                    p_head_el = OxmlElement("w:p")
                    if next_el is not None:
                        next_el.addprevious(p_head_el)
                    else:
                        doc._body._body.append(p_head_el)
                    p_head = Paragraph(p_head_el, doc)
                    p_head.paragraph_format.space_before = Pt(12)
                    p_head.paragraph_format.space_after = Pt(4)

                    question_text = po_q if po_q else f"{po_id}: {po_title}"
                    if not question_text.startswith(po_id):
                        question_text = f"{po_id}: {question_text}"

                    r_h = p_head.add_run(question_text)
                    r_h.font.name = "Times New Roman"
                    r_h.font.size = Pt(11)
                    r_h.font.bold = True

                    # 2. Insert Chart Image (Nothing below)
                    if chart_ref:
                        try:
                            chart_bytes = image_resolver(chart_ref)
                            if chart_bytes:
                                prep = prepare_image_for_docx(chart_bytes, max_width_in=5.2, max_height_in=3.4)
                                if prep:
                                    buf, w_in, h_in = prep
                                    p_img_el = OxmlElement("w:p")
                                    if next_el is not None:
                                        next_el.addprevious(p_img_el)
                                    else:
                                        doc._body._body.append(p_img_el)
                                    p_c = Paragraph(p_img_el, doc)
                                    p_c.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                                    p_c.paragraph_format.space_after = Pt(10)
                                    run_c = p_c.add_run()
                                    run_c.add_picture(buf, width=Inches(w_in), height=Inches(h_in))
                        except Exception as c_err:
                            logger.warning("Could not render chart for %s: %s", po_id, c_err)

        # Ensure target directory exists and save document
        os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)
        doc.save(output_filepath)
        return output_filepath
