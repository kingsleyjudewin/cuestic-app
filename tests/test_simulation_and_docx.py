import os
import tempfile
import docx
import pytest
from app.services.simulation_service import SimulationService, PO_FULL_DEFINITIONS, CLASS_COHORTS
from app.services.report_generator_service import ReportGeneratorService


def test_simulated_impact_analysis():
    """Verify simulated participant count, 8 cohorts, narrative, and 12 Q&A."""
    res = SimulationService.generate_simulated_impact_analysis(
        activity_title="GAUNTLET 2026",
        seed=101,
    )

    # 1. Total participants between 200 and 230
    count = res["participant_count"]
    assert 200 <= count <= 230

    # 2. 8 cohorts match exact names and sum to total
    class_dist = res["class_distribution"]
    assert len(class_dist) == 8
    cohort_names = [c["class_name"] for c in class_dist]
    assert cohort_names == CLASS_COHORTS

    total_sum = sum(c["count"] for c in class_dist)
    assert total_sum == count

    # 3. Class chart base64
    assert res["class_chart_base64"].startswith("data:image/png;base64,")

    # 4. 12 Impact Questions
    questions = res["questions"]
    assert len(questions) == 12
    for q in questions:
        assert q["question"] and q["answer"]
        assert "[Simulated]" in q["answer"]


def test_simulated_feedback_analysis():
    """Verify all 12 PO feedback charts, percentage brackets, and written interpretations."""
    participant_count = 219
    res = SimulationService.generate_simulated_feedback_analysis(
        participant_count=participant_count,
        seed=202,
    )

    po_results = res["po_results"]
    assert len(po_results) == 12
    assert len(res["summary_table"]) == 12

    for po_idx in range(1, 13):
        po_id = f"PO{po_idx}"
        assert po_id in po_results
        po_data = po_results[po_id]

        assert po_data["total_responses"] == participant_count
        counts = po_data["counts"]
        pcts = po_data["percentages"]

        # Exact 4 categories
        assert set(counts.keys()) == {"Excellent", "Very Good", "Fair", "Satisfactory"}
        assert sum(counts.values()) == participant_count

        # Target percentage brackets (allowing small rounding variations)
        assert 40 <= pcts["Excellent"] <= 65
        assert 25 <= pcts["Very Good"] <= 50
        assert 1 <= pcts["Fair"] <= 15
        assert 0 <= pcts["Satisfactory"] <= 8

        # Chart generated
        assert po_data["chart_base64"].startswith("data:image/png;base64,")

        # Interpretation generated
        assert po_data["interpretation"]
        assert "[Simulated Data]" in po_data["interpretation"]


def test_single_po_regeneration():
    """Verify individual PO chart regeneration."""
    single = SimulationService.generate_single_simulated_po(
        po_id="PO7",
        participant_count=215,
        seed=303,
    )
    assert single["po_id"] == "PO7"
    assert single["total_responses"] == 215
    assert sum(single["counts"].values()) == 215
    assert single["chart_base64"].startswith("data:image/png;base64,")
    assert "PO7" in single["interpretation"]


def test_report_generator_docx_embeds_all_charts():
    """Verify DOCX generation embeds class chart and all 12 PO charts into document."""
    impact_sim = SimulationService.generate_simulated_impact_analysis(participant_count=210, seed=404)
    feedback_sim = SimulationService.generate_simulated_feedback_analysis(participant_count=210, seed=505)

    report_data = {
        "general_information": {
            "title_of_activity": "GAUNTLET 2026",
            "type_of_activity": "Technical Workshop",
            "date": "02 November 2026",
            "time": "09:00 AM - 04:00 PM",
            "venue": "Block II Auditorium",
        },
        "participants": {
            "type_of_participants": "Engineering Undergraduates",
            "highlights": "Hands-on debugging and algorithmic synthesis challenges.",
            "summary": "Full-day workshop dedicated to collaborative electronic system engineering.",
            "key_takeaways": "Strong peer learning, modern tool adoption, and outcome attainment.",
        },
        "attendance_summary": {
            "total_rows_detected": 210,
            "total_verified_unique": 210,
            "class_distribution": impact_sim["class_distribution"],
            "is_simulated": True,
        },
        "class_chart_base64": impact_sim["class_chart_base64"],
        "class_distribution": impact_sim["class_distribution"],
        "impact_analysis": impact_sim["narrative"],
        "impact_questions": impact_sim["questions"],
        "feedback_analysis": feedback_sim["overall_interpretation"],
        "po_results": feedback_sim["po_results"],
        "feedback_data": feedback_sim,
        "is_simulated": True,
    }

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        ReportGeneratorService.generate_report_docx(report_data, tmp_path)
        assert os.path.exists(tmp_path)
        assert os.path.getsize(tmp_path) > 1_000_000  # Multi-megabyte document

        doc = docx.Document(tmp_path)
        # Verify embedded charts (12 PO feedback charts)
        total_images = sum(len(p._element.xpath(".//a:blip")) for p in doc.paragraphs)
        assert total_images == 12

        # Verify tables (general info and speaker tables; summary and individual PO tables removed per design)
        assert len(doc.tables) >= 5
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
