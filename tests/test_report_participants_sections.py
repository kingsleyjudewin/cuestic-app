"""Participants Profile / Highlights / Summary / Key Takeaways in the generated Activity Report DOCX."""
import io
import re

import docx

from app.services.feedback_analysis_service import FeedbackAnalysisService
from app.services.report_generator_service import ReportGeneratorService
from tests.test_ai_report_generator import doc_setup  # noqa: F401  (fixture)

HIGHLIGHTS = "\n".join(f"Highlight number {i} of the session." for i in range(1, 6))
TAKEAWAYS = "\n".join(f"Takeaway number {i} learned by students." for i in range(1, 6))
SUMMARY = "SOURCE CODE was organised by CUestIC.\nThe event fostered collaborative learning among coders."
MARK = "●"


def _flutter_payload_data(**overrides):
    """Same structure as _buildPayloadData() in activity_report_editor_screen.dart."""
    part = {
        "type_of_participants": "UG / PG Students & Faculty",
        "highlights": HIGHLIGHTS,
        "summary": SUMMARY,
        "key_takeaways": TAKEAWAYS,
    }
    part.update(overrides)
    return {
        "general_information": {"type_of_activity": "Workshop", "title_of_activity": "SOURCE CODE",
                                "date": "25 May 2026", "time": "5:30 PM", "venue": "Playground",
                                "collaborators": "CUestIC"},
        "speakers": [
            {"name": "Alice", "title": "Architect", "organization": "Intel", "presentation_title": "TinyML",
             "profile": "Alice leads TinyML research."},
            {"name": "Bob", "title": "Professor", "organization": "IIT", "presentation_title": "Edge AI",
             "profile": "Bob works on edge inference."},
        ],
        "participants": dict(part),
        "participants_profile": {
            "type_of_participants": part["type_of_participants"],
            "highlights_of_activity": part["highlights"],
            "summary_of_activities": part["summary"],
            "key_takeaways": part["key_takeaways"],
        },
        "speaker_profiles": ["Alice leads TinyML research.", "Bob works on edge inference."],
        "speaker_profile": "Alice leads TinyML research.\n\nBob works on edge inference.",
        "organiser": {"name": "Jerome", "designation": "Documentation", "signature": "Signed"},
    }


def _docx(tmp_path, data):
    out = tmp_path / "p.docx"
    ReportGeneratorService.generate_report_docx(data, str(out))
    return docx.Document(str(out))


def _table_with(doc, text, col=None):
    for t in doc.tables:
        cells = t.rows[0].cells if col is None else [t.rows[0].cells[col]]
        if any(text in c.text for c in cells):
            return t
    raise AssertionError(f"no table contains {text!r}")


def _bullets(cell):
    return [p.text for p in cell.paragraphs if p.text.strip()]


def test_participants_type_in_second_column(tmp_path):
    t = _table_with(_docx(tmp_path, _flutter_payload_data()), "Type of Participants", col=0)
    assert t.rows[0].cells[0].text.strip() == "Type of Participants"
    assert "UG / PG Students & Faculty" in t.rows[0].cells[1].text


def test_highlights_five_bullets_in_right_cell(tmp_path):
    doc = _docx(tmp_path, _flutter_payload_data())
    t = _table_with(doc, "Highlights of the", col=0)
    assert len(t.rows) == 1 and len(t.columns) == 2
    assert "Highlights of the" in t.rows[0].cells[0].text  # label intact
    bullets = _bullets(t.rows[0].cells[1])
    assert len(bullets) == 5
    assert all(b.startswith(MARK) for b in bullets)
    for i in range(1, 6):
        assert f"Highlight number {i} of the session." in bullets[i - 1]
    assert "Highlight number" not in t.rows[0].cells[0].text


def test_summary_full_width_cell_and_no_placeholder(tmp_path):
    doc = _docx(tmp_path, _flutter_payload_data())
    t = _table_with(doc, "SOURCE CODE was organised")
    assert len(t.columns) == 1 and len(t.rows) == 1
    assert [p.text for p in t.rows[0].cells[0].paragraphs] == SUMMARY.split("\n")
    assert "not provided" not in "\n".join(c.text for tb in doc.tables for r in tb.rows for c in r.cells)
    assert "Highlight number" not in t.rows[0].cells[0].text  # sections use their own source fields


def test_key_takeaways_five_bullets_in_right_cell(tmp_path):
    doc = _docx(tmp_path, _flutter_payload_data())
    t = _table_with(doc, "Key Takeaways", col=0)
    assert t.rows[0].cells[0].text.strip() == "Key Takeaways"
    bullets = _bullets(t.rows[0].cells[1])
    assert len(bullets) == 5 and all(b.startswith(MARK) for b in bullets)
    assert "Takeaway number 3" in bullets[2]
    assert "Highlight number" not in t.rows[0].cells[1].text


def test_list_values_and_alt_keys_are_supported(tmp_path):
    data = _flutter_payload_data()
    data.pop("participants")
    data["participants_profile"].update(highlights_of_activity=["H one", "H two"], key_takeaways=["K one", "K two"])
    doc = _docx(tmp_path, data)
    assert len(_bullets(_table_with(doc, "Highlights of the", col=0).rows[0].cells[1])) == 2
    assert len(_bullets(_table_with(doc, "Key Takeaways", col=0).rows[0].cells[1])) == 2


def test_placeholders_only_when_genuinely_empty(tmp_path):
    doc = _docx(tmp_path, _flutter_payload_data(highlights="", summary="", key_takeaways=""))
    text = "\n".join(c.text for tb in doc.tables for r in tb.rows for c in r.cells)
    assert "Highlights of the Activity were not provided" in text
    assert "Summary of the Activities was not provided" in text
    assert "Key Takeaways were not provided" in text
    # one empty field must not affect the others
    doc = _docx(tmp_path, _flutter_payload_data(summary=""))
    text = "\n".join(c.text for tb in doc.tables for r in tb.rows for c in r.cells)
    assert "Summary of the Activities was not provided" in text
    assert "Highlights of the Activity were not provided" not in text
    assert "Takeaway number 5" in text


def test_flutter_payload_survives_api_save_and_docx_generation(client, doc_setup):
    """create -> update -> generate -> download using the exact Flutter payload structure."""
    headers = {"Authorization": f"Bearer {doc_setup['doc_token']}"}
    data = _flutter_payload_data()
    res = client.post("/api/v1/documentation/reports", json={"title": "SOURCE CODE", "data": data}, headers=headers)
    assert res.status_code == 201
    rid = res.get_json()["data"]["id"]
    saved = client.get(f"/api/v1/documentation/reports/{rid}", headers=headers).get_json()["data"]["data"]
    for key in ("participants", "participants_profile"):
        assert saved[key] == data[key]  # nothing dropped or overwritten by the backend

    data["participants"]["summary"] = SUMMARY + "\nAn extra paragraph added on edit."
    assert client.put(f"/api/v1/documentation/reports/{rid}", json={"title": "SOURCE CODE", "data": data},
                      headers=headers).status_code == 200
    assert client.post(f"/api/v1/documentation/reports/{rid}/generate-docx", headers=headers).status_code == 200
    dl = client.get(f"/api/v1/documentation/reports/{rid}/download-docx", headers=headers)
    doc = docx.Document(io.BytesIO(dl.data))
    assert "An extra paragraph added on edit." in _table_with(doc, "SOURCE CODE was organised").rows[0].cells[0].text
    assert len(_bullets(_table_with(doc, "Key Takeaways", col=0).rows[0].cells[1])) == 5
    assert len(_bullets(_table_with(doc, "Highlights of the", col=0).rows[0].cells[1])) == 5


def test_full_report_with_everything(tmp_path):
    _, chart = FeedbackAnalysisService.generate_po_pie_chart(
        "PO1", "Engineering Knowledge", {"Fair": 2, "Satisfactory": 5, "Very Good": 20, "Excellent": 30})
    data = _flutter_payload_data()
    data["impact_analysis"] = "Custom impact note."
    data["po_results"] = {"PO1": {"po_id": "PO1", "po_title": "Engineering Knowledge", "positive_percentage": 87.7,
                                  "chart_base64": chart, "total_responses": 220}}
    out = tmp_path / "full.docx"
    ReportGeneratorService.generate_report_docx(data, str(out))
    doc = docx.Document(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    for marker in ("Speaker Details 1", "Speaker Details 2", "Alice leads TinyML research.", "Bob works on edge inference.",
                   "Annexure:", "Impact Analysis:", "Feedback Analysis:", "Summary of the Activities:"):
        assert marker in text, marker
    assert not re.search(r"not provided", "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells))
    assert len(doc.inline_shapes) >= 1
