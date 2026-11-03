import io
import docx
from PIL import Image
from app.services.report_generator_service import (
    ReportGeneratorService,
    prepare_image_for_docx,
    extract_images_from_data,
)


def test_prepare_image_transparency_and_aspect_fit():
    # 1. Test RGBA image: ensure transparent pixels are composited onto clean white
    rgba_im = Image.new("RGBA", (100, 100), (0, 0, 0, 0))  # fully transparent
    rgba_buf = io.BytesIO()
    rgba_im.save(rgba_buf, format="PNG")
    rgba_bytes = rgba_buf.getvalue()

    result = prepare_image_for_docx(rgba_bytes, max_width_in=6.0, max_height_in=8.0)
    assert result is not None
    buf, w_in, h_in = result
    out_im = Image.open(buf)
    assert out_im.mode == "RGB"
    # Should be solid white, not black or distorted with artifacts
    assert out_im.getpixel((50, 50)) == (255, 255, 255)
    assert w_in == 6.0
    assert h_in == 6.0


def test_prepare_tall_image_aspect_ratio_does_not_overflow():
    # Tall image: 720 x 1600 (aspect ratio < 0.5)
    tall_im = Image.new("RGB", (720, 1600), (50, 100, 150))
    tall_buf = io.BytesIO()
    tall_im.save(tall_buf, format="JPEG")

    result = prepare_image_for_docx(tall_buf.getvalue(), max_width_in=6.0, max_height_in=8.0)
    assert result is not None
    _, w_in, h_in = result
    # Height must strictly be capped at 8.0 inches so it never overflows the Word page
    assert h_in == 8.0
    assert w_in < 6.0
    assert round(w_in, 1) == 3.6


def test_attendance_sheets_proper_alignment_and_neat_order(tmp_path):
    # Generate 3 simulated attendance sheets
    att_sheets = []
    for i in range(3):
        im = Image.new("RGB", (600, 800), (240 + i, 240 + i, 240 + i))
        b = io.BytesIO()
        im.save(b, format="PNG")
        att_sheets.append(b.getvalue())

    report_data = {
        "title": "Annual Department Symposium 2026",
        "general_information": {
            "title_of_activity": "Annual Department Symposium 2026",
            "type_of_activity": "National Symposium",
            "date": "10 Nov 2026",
            "time": "10:00 AM",
            "venue": "Main Hall",
        },
        "annexures": {
            "attendance_sheets_base64": att_sheets,
        },
    }

    out_file = str(tmp_path / "test_report_attendance.docx")
    ReportGeneratorService.generate_report_docx(
        report_data=report_data,
        output_filepath=out_file,
        image_resolver=lambda x: x,
    )

    doc = docx.Document(out_file)
    p_texts = [p.text for p in doc.paragraphs if p.text.strip()]

    # Verify heading and captions
    assert "Attendance list of participants:" in p_texts
    assert "Attendance Sheet — Page 1 of 3" in p_texts
    assert "Attendance Sheet — Page 2 of 3" in p_texts
    assert "Attendance Sheet — Page 3 of 3" in p_texts

    # Verify all 3 attendance drawings are present
    blips = [p._element.xpath(".//a:blip/@r:embed") for p in doc.paragraphs if p._element.xpath(".//a:blip/@r:embed")]
    assert len(blips) == 3
