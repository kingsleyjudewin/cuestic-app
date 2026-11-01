import os
import io
import logging
from typing import Optional, List
from datetime import datetime
import docx
from docx.shared import Pt, Inches
from docx.enum.text import WD_BREAK
from PIL import Image

logger = logging.getLogger(__name__)

TEMPLATE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "templates", "template_cuestic_document.docx")
)


def _set_cell_text(cell, text: str, bold: bool = False, font_name: str = "Times New Roman", font_size_pt: int = 12, line_spacing: float = 1.15):
    """Set cell text with explicit font family, size, line spacing, preserving paragraph formatting."""
    cell.text = ""
    clean_text = (text or "").strip()
    if not clean_text:
        return

    # Split into clean paragraphs
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


def _add_styled_paragraph(doc, text: str, bold: bool = False, font_size_pt: int = 12, insert_before_p=None):
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
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(font_size_pt)
    run.font.bold = bold
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
        # Check fallback in Documents folder
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
                _set_cell_text(t0.rows[2].cells[1], date_str)
                _set_cell_text(t0.rows[3].cells[1], time_str)
                _set_cell_text(t0.rows[4].cells[1], venue_str)

            if collaborators_str:
                if len(t0.rows) > 5:
                    _set_cell_text(t0.rows[5].cells[1], collaborators_str)
                else:
                    new_row = t0.add_row()
                    _set_cell_text(new_row.cells[0], "Collaborators / Student Chapter", bold=True)
                    _set_cell_text(new_row.cells[1], collaborators_str)

        # -------------------------------------------------------------
        # Section 2 — Speaker Details (Table 1)
        # -------------------------------------------------------------
        raw_speakers = report_data.get("speakers") or []
        valid_speakers = [
            s for s in raw_speakers
            if isinstance(s, dict) and any(str(s.get(k, "")).strip() for k in ("name", "title", "position", "organization"))
        ]
        if not valid_speakers:
            valid_speakers = [{
                "name": "Internal Faculty & Student Coordinators",
                "title": "Faculty & Student Coordinators",
                "organization": "Department of Electronics and Communication Engineering",
                "presentation_title": title_of_activity,
            }]

        if len(doc.tables) > 1:
            t1 = doc.tables[1]
            spk1 = valid_speakers[0]
            spk1_title = spk1.get("title") or spk1.get("position") or spk1.get("designation") or ""
            spk1_org = spk1.get("organization") or spk1.get("institution") or ""
            spk1_pres = spk1.get("presentation_title") or spk1.get("topic") or spk1.get("title_of_presentation") or title_of_activity

            _set_cell_text(t1.rows[0].cells[1], spk1.get("name", ""))
            _set_cell_text(t1.rows[1].cells[1], spk1_title)
            _set_cell_text(t1.rows[2].cells[1], spk1_org)
            _set_cell_text(t1.rows[3].cells[1], spk1_pres)

            # Additional speakers append 4 rows each
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

        # Table 2: Type of Participants
        if len(doc.tables) > 2 and len(doc.tables[2].rows) >= 1:
            _set_cell_text(doc.tables[2].rows[0].cells[1], type_of_participants)

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
            from docx.oxml import OxmlElement
            from docx.text.paragraph import Paragraph

            if next_elem is not None:
                new_p_elem = OxmlElement('w:p')
                next_elem.addprevious(new_p_elem)
                p_bio = Paragraph(new_p_elem, doc)
            else:
                p_bio = doc.add_paragraph()

            p_bio.paragraph_format.line_spacing = 1.15
            p_bio.paragraph_format.space_after = Pt(8)
            content_to_insert = (
                speaker_profile.strip()
                if speaker_profile and speaker_profile.strip()
                else f"Event organized and coordinated by the Department of Electronics and Communication Engineering, CUestIC, CHRIST (Deemed to be University)."
            )
            run = p_bio.add_run(content_to_insert)
            run.font.name = "Times New Roman"
            run.font.size = Pt(12)
            if not speaker_profile or not speaker_profile.strip():
                run.font.italic = True

        # -------------------------------------------------------------
        # Section 6 — Annexures: Photos, Attendance, Poster, Certificates, Feedback, Impact
        # -------------------------------------------------------------
        annexures = report_data.get("annexures") or {}
        from docx.oxml import OxmlElement
        from docx.text.paragraph import Paragraph

        user_feedback_text = (report_data.get("feedback_analysis") or "").strip()
        user_has_feedback = bool(user_feedback_text)
        user_has_certificate = bool(annexures.get("certificate") or annexures.get("certificates") or annexures.get("sample_certificate"))

        # 1. Purge all template dummy drawings (rId2 to rId16), placeholder text, and simulated feedback
        to_remove = []
        in_feedback_block = False
        in_certificate_block = False

        for p in list(doc.paragraphs):
            txt = p.text.strip()

            if "Feedback Analysis:" in txt:
                in_feedback_block = True
                if not user_has_feedback:
                    to_remove.append(p)
                continue

            if "Impact Analysis:" in txt:
                in_feedback_block = False

            if in_feedback_block:
                # Always remove template dummy feedback chart drawings and filler paragraphs
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

            # Remove old template blips (rId2: old poster, rId3: old cert, rId4-16: old feedback charts)
            blip_rids = p._element.xpath('.//a:blip/@r:embed')
            if blip_rids and any(rid in ('rId2', 'rId3', 'rId4', 'rId5', 'rId6', 'rId7', 'rId8', 'rId9', 'rId10', 'rId11', 'rId12', 'rId13', 'rId14', 'rId15', 'rId16') for rid in blip_rids):
                to_remove.append(p)

        for p in to_remove:
            try:
                p._element.getparent().remove(p._element)
            except Exception:
                pass

        # Clean consecutive empty paragraphs (more than 1 in a row) to remove phantom blank pages
        last_was_empty = False
        for p in list(doc.paragraphs):
            if not p.text.strip() and not p._element.xpath('.//w:drawing'):
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
            elif "Feedback Analysis:" in txt:
                feedback_marker_p = p
            elif "Impact Analysis:" in txt:
                impact_marker_p = p
                # Look for old semiconductor paragraphs to replace
                for scan_p in doc.paragraphs[idx:min(idx + 5, len(doc.paragraphs))]:
                    if "technical talk significantly enhanced" in scan_p.text:
                        impact_body_p1 = scan_p
                    elif "Furthermore, the talk inspired" in scan_p.text:
                        impact_body_p2 = scan_p

        # 2. Activity Photos
        activity_photos = annexures.get("photos") or annexures.get("photos_base64") or []
        if photos_marker_p:
            photos_marker_p.text = "Photos of Activity:"
            inserted_photos = 0
            if activity_photos and image_resolver:
                next_el = photos_marker_p._element.getnext()
                for photo_ref in activity_photos:
                    try:
                        img_data = image_resolver(photo_ref)
                        if img_data:
                            new_el = OxmlElement('w:p')
                            if next_el is not None:
                                next_el.addprevious(new_el)
                            else:
                                doc._body._body.append(new_el)
                            p_img = Paragraph(new_el, doc)
                            p_img.paragraph_format.space_after = Pt(12)
                            p_img.paragraph_format.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
                            run = p_img.add_run()
                            run.add_picture(io.BytesIO(img_data), width=Inches(5.5))
                            inserted_photos += 1
                    except Exception as e:
                        logger.warning("Could not insert activity photo: %s", e)

            if inserted_photos == 0:
                photos_marker_p.text = "Photos of Activity: Documented and archived in the Department Event Repository."

        # 3. Attendance List
        attendance_pages = annexures.get("attendance_sheets") or annexures.get("attendance_pages") or []
        if attendance_marker_p:
            attendance_marker_p.text = "Attendance list of participants:"
            inserted_att = 0
            if attendance_pages and image_resolver:
                next_el = attendance_marker_p._element.getnext()
                for idx, att_ref in enumerate(attendance_pages):
                    try:
                        img_data = image_resolver(att_ref)
                        if img_data:
                            new_el = OxmlElement('w:p')
                            if next_el is not None:
                                next_el.addprevious(new_el)
                            else:
                                doc._body._body.append(new_el)
                            p_att = Paragraph(new_el, doc)
                            p_att.paragraph_format.space_after = Pt(8)
                            p_att.paragraph_format.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
                            run = p_att.add_run()
                            run.add_picture(io.BytesIO(img_data), width=Inches(6.0))
                            if idx < len(attendance_pages) - 1:
                                p_att.add_run().add_break(WD_BREAK.PAGE)
                            inserted_att += 1
                    except Exception as e:
                        logger.warning("Could not insert attendance sheet: %s", e)

            if inserted_att == 0:
                attendance_marker_p.text = "Attendance list of participants: Verified and preserved in departmental physical records."

        # 4. Poster Image
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
                    img_data = image_resolver(poster_ref)
                    if img_data:
                        next_el = poster_marker_p._element.getnext()
                        new_el = OxmlElement('w:p')
                        if next_el is not None:
                            next_el.addprevious(new_el)
                        else:
                            doc._body._body.append(new_el)
                        p_poster = Paragraph(new_el, doc)
                        p_poster.paragraph_format.space_after = Pt(12)
                        p_poster.paragraph_format.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
                        run = p_poster.add_run()
                        run.add_picture(io.BytesIO(img_data), width=Inches(5.5))
                        inserted_poster = True
                except Exception as e:
                    logger.warning("Could not insert poster image: %s", e)

            if not inserted_poster:
                poster_marker_p.text = "Poster: Archived with Department Media Team."

        # 5. Feedback Analysis (Only if explicitly provided by user, never simulated)
        if user_has_feedback and feedback_marker_p:
            feedback_marker_p.text = "Feedback Analysis:"
            next_el = feedback_marker_p._element.getnext()
            new_el = OxmlElement('w:p')
            if next_el is not None:
                next_el.addprevious(new_el)
            else:
                doc._body._body.append(new_el)
            p_fb = Paragraph(new_el, doc)
            p_fb.paragraph_format.line_spacing = 1.15
            p_fb.paragraph_format.space_after = Pt(6)
            run = p_fb.add_run(user_feedback_text)
            run.font.name = "Times New Roman"
            run.font.size = Pt(12)

        # 6. Impact Analysis narrative (clean replacement of semiconductor text)
        act_title_clean = title_of_activity[4:] if title_of_activity.lower().startswith("the ") else title_of_activity
        impact_text = (
            report_data.get("impact_analysis")
            or f"The {act_title_clean} provided practical engagement, collaborative teamwork, and analytical problem-solving experience for students of the Department of Electronics and Communication Engineering."
        )

        if impact_body_p1:
            impact_body_p1.text = ""
            run = impact_body_p1.add_run(impact_text)
            run.font.name = "Times New Roman"
            run.font.size = Pt(12)
            impact_body_p1.paragraph_format.line_spacing = 1.15
            impact_body_p1.paragraph_format.space_after = Pt(6)
        elif impact_marker_p:
            next_el = impact_marker_p._element.getnext()
            new_el = OxmlElement('w:p')
            if next_el is not None:
                next_el.addprevious(new_el)
            else:
                doc._body._body.append(new_el)
            p_imp = Paragraph(new_el, doc)
            p_imp.paragraph_format.line_spacing = 1.15
            p_imp.paragraph_format.space_after = Pt(6)
            run = p_imp.add_run(impact_text)
            run.font.name = "Times New Roman"
            run.font.size = Pt(12)

        if impact_body_p2:
            try:
                impact_body_p2._element.getparent().remove(impact_body_p2._element)
            except Exception:
                impact_body_p2.text = ""

        # Ensure target directory exists and save document
        os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)
        doc.save(output_filepath)
        logger.info("Successfully generated report DOCX at %s", output_filepath)
        return output_filepath
        if submit_marker_p and sub_info.get("name"):
            # Update submission lines
            pass  # Template has standard faculty name, customized if provided

        # Ensure target directory exists and save document
        os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)
        doc.save(output_filepath)
        logger.info("Successfully generated report DOCX at %s", output_filepath)
        return output_filepath
