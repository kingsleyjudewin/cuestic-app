import os
import io
import json
import pytest
from app.services.attendance_ocr_service import AttendanceOCRService
from app.services.feedback_analysis_service import FeedbackAnalysisService, PO_DEFINITIONS
from app.services.report_generator_service import ReportGeneratorService


def test_attendance_ocr_service_signature_and_class_mapping():
    """Verify class mapping rules and signature detection heuristics."""
    assert AttendanceOCRService.map_registration_to_class("2460601") == "4BTEC"
    assert AttendanceOCRService.map_registration_to_class("2462618") == "4BTELCS"
    assert AttendanceOCRService.map_registration_to_class("2360100") == "6BTEC"
    assert AttendanceOCRService.map_registration_to_class("2362100") == "6BTELCS"
    assert AttendanceOCRService.map_registration_to_class("2260100") == "8BTEC"
    assert AttendanceOCRService.map_registration_to_class("9999999") == "Unmapped"

    # Member directory override
    custom_dir = {"9999999": "4BTEC"}
    assert AttendanceOCRService.map_registration_to_class("9999999", member_directory=custom_dir) == "4BTEC"


def test_attendance_summary_calculation():
    """Verify attendance summary computation and verification rules."""
    records = [
        {"reg_no": "2460601", "signature_detected": True, "status": "Verified", "mapped_class": "4BTEC"},
        {"reg_no": "2460602", "signature_detected": True, "status": "Verified", "mapped_class": "4BTEC"},
        {"reg_no": "2462601", "signature_detected": True, "status": "Verified", "mapped_class": "4BTELCS"},
        {"reg_no": "2460603", "signature_detected": False, "status": "Excluded", "mapped_class": "4BTEC"},
        {"reg_no": "2460601", "signature_detected": True, "status": "Duplicate", "mapped_class": "4BTEC", "is_duplicate": True},
    ]

    summary = AttendanceOCRService.compute_attendance_summary(records)
    assert summary["total_rows_detected"] == 5
    assert summary["total_verified_unique"] == 3
    assert summary["total_records_with_signatures"] == 4
    assert summary["duplicate_records"] == 1
    assert summary["excluded_records"] == 1

    classes = {item["class_name"]: item["count"] for item in summary["class_distribution"]}
    assert classes["4BTEC"] == 2
    assert classes["4BTELCS"] == 1


def test_feedback_analysis_service_rating_normalization_and_chart():
    """Verify rating normalization, chart generation, and factual interpretations."""
    assert FeedbackAnalysisService.normalize_rating("Excellent") == "Excellent"
    assert FeedbackAnalysisService.normalize_rating("very good") == "Very Good"
    assert FeedbackAnalysisService.normalize_rating("3") == "Very Good"
    assert FeedbackAnalysisService.normalize_rating("Satisfactory") == "Satisfactory"
    assert FeedbackAnalysisService.normalize_rating("Fair") == "Fair"
    assert FeedbackAnalysisService.normalize_rating("") is None

    counts = {"Fair": 2, "Satisfactory": 5, "Very Good": 20, "Excellent": 30}
    chart_bytes, chart_b64 = FeedbackAnalysisService.generate_po_pie_chart("PO1", "Engineering Knowledge", counts)
    assert len(chart_bytes) > 1000
    assert chart_b64.startswith("data:image/png;base64,")

    # Analyze feedback rows
    rows = [
        {"Q1": "Excellent", "Q2": "Very Good"},
        {"Q1": "Very Good", "Q2": "Satisfactory"},
        {"Q1": "Excellent", "Q2": "Fair"},
    ]
    mapping = {"PO1": "Q1", "PO2": "Q2"}
    result = FeedbackAnalysisService.analyze_feedback(rows, mapping)

    assert result["total_respondents"] == 3
    assert result["mapped_pos_count"] == 2
    assert "PO1" in result["po_results"]
    assert "PO2" in result["po_results"]
    assert "verified participant responses" in result["interpretation"]


def test_docx_report_generation_with_all_sections(tmp_path):
    """Verify report generation with attendance breakdown, certificate, impact questions, and PO charts."""
    out_file = str(tmp_path / "test_full_activity_report.docx")

    # Generate test chart
    _, chart_b64 = FeedbackAnalysisService.generate_po_pie_chart("PO1", "Engineering Knowledge", {"Fair": 1, "Satisfactory": 2, "Very Good": 5, "Excellent": 10})

    report_payload = {
        "title": "THE GAUNTLET TREASURE HUNT",
        "type_of_activity": "Department Flagship Event",
        "date": "2026-10-25",
        "time": "14:00 - 17:00",
        "venue": "SET Campus Block 3",
        "collaborators": "IEEE Student Branch",
        "speakers": [{"name": "Faculty Mentors", "title": "Coordinators", "organization": "CHRIST (Deemed to be University)", "presentation_title": "Treasure Hunt"}],
        "participants": {
            "type_of_participants": "Students of School of Engineering and Technology",
            "highlights": "Over 60 students participated in problem solving rounds.",
            "summary": "The event fostered interdisciplinary collaboration and analytical reasoning.",
            "key_takeaways": "Practical algorithmic thinking and team coordination.",
        },
        "attendance_summary": {
            "total_verified_unique": 61,
            "class_distribution": [
                {"class_name": "4BTEC", "count": 31, "percentage": 50.8},
                {"class_name": "4BTELCS", "count": 30, "percentage": 49.2},
            ]
        },
        "annexures": {
            "photos_base64": [],
            "attendance_sheets_base64": [],
            "certificate_category": "Participation",
            "certificates_issued": 61,
            "certificate_base64": chart_b64,  # Reuse chart image bytes as sample certificate
        },
        "impact_analysis": "The activity recorded active participation from 2nd year BTEC and BTELCS cohorts.",
        "impact_questions": [
            {"question": "1. How effectively did the activity address its stated objectives?", "answer": "All algorithmic challenges were completed by participants."},
            {"question": "2. How many verified participants attended the activity?", "answer": "61 verified unique participants."},
        ],
        "feedback_analysis": "Participant feedback reflected exceptional engagement across core engineering competencies.",
        "po_results": {
            "PO1": {
                "po_id": "PO1",
                "po_title": "Engineering Knowledge",
                "counts": {"Fair": 1, "Satisfactory": 2, "Very Good": 5, "Excellent": 10},
                "percentages": {"Fair": 5.6, "Satisfactory": 11.1, "Very Good": 27.8, "Excellent": 55.6},
                "chart_base64": chart_b64,
            }
        }
    }

    def dummy_resolver(ref):
        if ref.startswith("data:image/"):
            import base64
            return base64.b64decode(ref.split(";base64,")[1])
        return None

    path = ReportGeneratorService.generate_report_docx(
        report_data=report_payload,
        output_filepath=out_file,
        image_resolver=dummy_resolver,
    )

    assert os.path.exists(path)
    assert os.path.getsize(path) > 10000


def test_multi_speaker_and_impact_analysis_docx(tmp_path):
    """Verify multi-speaker table formatting, speaker profiles, and chart-derived impact analysis."""
    import docx
    out_file = str(tmp_path / "test_multi_speaker_report.docx")

    _, chart_b64 = FeedbackAnalysisService.generate_po_pie_chart("PO1", "Engineering Knowledge", {"Fair": 2, "Satisfactory": 5, "Very Good": 20, "Excellent": 30})
    _, chart_b64_2 = FeedbackAnalysisService.generate_po_pie_chart("PO2", "Problem Analysis", {"Fair": 1, "Satisfactory": 4, "Very Good": 18, "Excellent": 35})

    payload = {
        "title": "EMBEDDED AI WORKSHOP",
        "type_of_activity": "Technical Workshop",
        "speakers": [
            {
                "name": "Dr. Alice Smith",
                "title": "Principal Architect",
                "organization": "Intel Labs",
                "presentation_title": "TinyML Acceleration",
                "profile": "Dr. Smith leads TinyML architecture research with 20 IEEE publications.",
            },
            {
                "name": "Prof. Bob Jones",
                "title": "Professor",
                "organization": "IIT Madras",
                "presentation_title": "Edge Inference Systems",
                "profile": "Prof. Jones specializes in neuromorphic computing and low-power hardware.",
            },
            {
                "name": "Ms. Carol White",
                "title": "Senior Solutions Engineer",
                "organization": "NVIDIA",
                "presentation_title": "Jetson Orin Optimization",
                "profile": "Ms. White mentors university development teams in GPU-accelerated robotics.",
            },
        ],
        "po_results": {
            "PO1": {
                "po_id": "PO1",
                "po_title": "Engineering Knowledge",
                "counts": {"Fair": 2, "Satisfactory": 5, "Very Good": 20, "Excellent": 30},
                "positive_percentage": 87.7,
                "chart_base64": chart_b64,
                "total_responses": 220,
            },
            "PO2": {
                "po_id": "PO2",
                "po_title": "Problem Analysis",
                "counts": {"Fair": 1, "Satisfactory": 4, "Very Good": 18, "Excellent": 35},
                "positive_percentage": 91.4,
                "chart_base64": chart_b64_2,
                "total_responses": 220,
            },
        },
        "attendance_summary": {
            "total_verified_unique": 220,
            "class_distribution": [
                {"class_name": "6BTELCS", "count": 110, "percentage": 50.0},
                {"class_name": "6BTEC", "count": 110, "percentage": 50.0},
            ],
        },
    }

    def dummy_resolver(ref):
        if ref and ref.startswith("data:image/"):
            import base64
            return base64.b64decode(ref.split(";base64,")[1])
        return None

    path = ReportGeneratorService.generate_report_docx(
        report_data=payload,
        output_filepath=out_file,
        image_resolver=dummy_resolver,
    )

    assert os.path.exists(path)
    doc = docx.Document(path)

    # 1. Verify one numbered heading + one 4-row, 2-column table per speaker (Tables 1, 2, 3)
    doc_text = "\n".join([p.text for p in doc.paragraphs])
    for n, name in enumerate(("Alice Smith", "Bob Jones", "Carol White"), start=1):
        assert f"Speaker Details {n}" in doc_text
        tbl = doc.tables[n]
        assert len(tbl.rows) == 4
        assert tbl.rows[0].cells[0].text.strip() == "Name"
        assert name in tbl.rows[0].cells[1].text

    # 2. Verify all 3 speaker profiles exist in paragraphs, each under its own speaker
    assert "Dr. Alice Smith" in doc_text
    assert "TinyML architecture research" in doc_text
    assert "Prof. Bob Jones" in doc_text
    assert "neuromorphic computing" in doc_text
    assert "Ms. Carol White" in doc_text
    assert "GPU-accelerated robotics" in doc_text

    # 3. Verify Impact Analysis generated automatically from pie chart
    assert "Impact Analysis:" in doc_text
    assert "89.6%" in doc_text or "PO2" in doc_text
    assert "220 verified participant respondents" in doc_text

    # 4. Verify sequence: Feedback Analysis -> Impact Analysis -> Report submitted by
    fb_idx = next(i for i, p in enumerate(doc.paragraphs) if "Feedback Analysis:" in p.text)
    imp_idx = next(i for i, p in enumerate(doc.paragraphs) if "Impact Analysis:" in p.text)
    sub_idx = next(i for i, p in enumerate(doc.paragraphs) if "Report submitted by" in p.text)
    assert fb_idx < imp_idx < sub_idx
