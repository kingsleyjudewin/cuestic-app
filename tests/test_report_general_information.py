"""Regression tests: General Information rows of the generated Activity Report DOCX."""
import docx

from app.services.feedback_analysis_service import FeedbackAnalysisService
from app.services.report_generator_service import ReportGeneratorService


def _gen(tmp_path, payload):
    out = tmp_path / "gi.docx"
    ReportGeneratorService.generate_report_docx(payload, str(out))
    return docx.Document(str(out))


def _rows(doc):
    """General Information table as {label: value}."""
    return {r.cells[0].text.strip(): r.cells[1].text.strip() for r in doc.tables[0].rows}


def _info(**kw):
    base = {
        "type_of_activity": "Workshop",
        "title_of_activity": "AI and Cybersecurity Workshop",
        "date": "17 November 2026",
        "time": "10:00 AM – 01:00 PM",
        "venue": "Block 2 Seminar Hall",
    }
    base.update(kw)
    return {"general_information": base}


def test_all_fields_land_in_their_own_rows(tmp_path):
    rows = _rows(_gen(tmp_path, _info()))
    assert rows == {
        "Type of Activity": "Workshop",
        "Title of the Activity": "AI and Cybersecurity Workshop",
        "Date/s": "17 November 2026",
        "Time": "10:00 AM – 01:00 PM",
        "Venue": "Block 2 Seminar Hall",
    }


def test_time_only_in_time_row_and_venue_only_in_venue_row(tmp_path):
    rows = _rows(_gen(tmp_path, _info()))
    assert "10:00" not in rows["Date/s"] and "Hall" not in rows["Time"]
    assert rows["Time"] == "10:00 AM – 01:00 PM"
    assert rows["Venue"] == "Block 2 Seminar Hall"


def test_missing_optional_field_does_not_shift_rows(tmp_path):
    rows = _rows(_gen(tmp_path, _info(time="")))
    assert rows["Time"] == ""
    assert rows["Date/s"] == "17 November 2026"
    assert rows["Venue"] == "Block 2 Seminar Hall"

    rows = _rows(_gen(tmp_path, _info(date="")))
    assert rows["Date/s"] == "" and rows["Time"] == "10:00 AM – 01:00 PM" and rows["Venue"] == "Block 2 Seminar Hall"


def test_collaborators_never_replace_venue(tmp_path):
    rows = _rows(_gen(tmp_path, _info(collaborators="IEEE Student Branch")))
    assert rows["Venue"] == "Block 2 Seminar Hall"
    assert "IEEE" not in "".join(rows.values())
    # empty venue must not be back-filled with collaborators either
    rows = _rows(_gen(tmp_path, _info(venue="", collaborators="IEEE Student Branch")))
    assert rows["Venue"] == ""


def test_alternate_payload_keys_are_still_accepted(tmp_path):
    rows = _rows(_gen(tmp_path, {"general_information": {
        "title_of_activity": "T", "dates": "1 Jan", "timings": "9 AM", "location": "Lab 1"}}))
    assert (rows["Date/s"], rows["Time"], rows["Venue"]) == ("1 Jan", "9 AM", "Lab 1")


def test_full_report_regression(tmp_path):
    _, chart = FeedbackAnalysisService.generate_po_pie_chart(
        "PO1", "Engineering Knowledge", {"Fair": 2, "Satisfactory": 5, "Very Good": 20, "Excellent": 30})
    payload = _info(collaborators="IEEE")
    payload.update({
        "speakers": [
            {"name": "Alice", "title": "Architect", "organization": "Intel", "presentation_title": "TinyML",
             "profile": "Alice leads TinyML research."},
            {"name": "Bob", "title": "Professor", "organization": "IIT", "presentation_title": "Edge AI",
             "profile": "Bob works on edge inference."},
        ],
        "participants": {
            "type_of_participants": "Students",
            "summary": "Summary paragraph one.",
            "key_takeaways": "- k1\n- k2\n- k3\n- k4\n- k5",
        },
        "impact_analysis": "Custom impact note.",
        "po_results": {"PO1": {"po_id": "PO1", "po_title": "Engineering Knowledge",
                               "positive_percentage": 87.7, "chart_base64": chart, "total_responses": 220}},
    })
    doc = _gen(tmp_path, payload)
    rows = _rows(doc)
    assert rows["Time"] == "10:00 AM – 01:00 PM" and rows["Venue"] == "Block 2 Seminar Hall"

    text = "\n".join(p.text for p in doc.paragraphs)
    for marker in ("Speaker Details 1", "Speaker Details 2", "Speaker Profile:", "Impact Analysis:",
                   "Feedback Analysis:", "Annexure:", "Alice leads TinyML research.", "Bob works on edge inference."):
        assert marker in text, marker
    assert len(doc.tables[1].rows) == 4 and len(doc.tables[2].rows) == 4
    assert "Alice" in doc.tables[1].rows[0].cells[1].text and "Bob" in doc.tables[2].rows[0].cells[1].text

    summary_tbl = next(t for t in doc.tables if "Summary paragraph one." in t.rows[0].cells[0].text)
    assert summary_tbl is not None
    kt = next(t for t in doc.tables if "Key Takeaways" in t.rows[0].cells[0].text).rows[0].cells[1]
    assert len(kt.paragraphs) == 5
    assert len(doc.inline_shapes) >= 1  # PO chart image embedded
