"""PDF → PNG page rendering via Poppler's `pdftoppm`, with explicit, user-safe errors."""
import glob
import logging
import os
import shutil
import subprocess
import tempfile
from typing import List

from app.utils.errors import AppError

logger = logging.getLogger(__name__)

MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", "40"))


class PdfConversionError(AppError):
    """Raised when a PDF cannot be rendered to images."""
    status_code = 422
    code = "PDF_CONVERSION_FAILED"


def is_pdf(data: bytes) -> bool:
    return bool(data) and data[:5] == b"%PDF-"


def pdftoppm_available() -> bool:
    return shutil.which("pdftoppm") is not None


def pdf_to_png_pages(pdf_bytes: bytes, dpi: int = 150, timeout: int = 45) -> List[bytes]:
    """Render each PDF page (up to MAX_PDF_PAGES) to PNG bytes. Raises PdfConversionError."""
    exe = shutil.which("pdftoppm")
    if not exe:
        logger.error("PDF conversion unavailable: 'pdftoppm' not found on PATH (install poppler-utils).")
        raise PdfConversionError(
            "PDF processing is not available on this server right now. "
            "Please upload the pages as images (JPG/PNG) or contact the administrator.",
            code="PDF_TOOL_MISSING",
            status_code=503,
        )

    with tempfile.TemporaryDirectory(prefix="pdfconv-") as tmpdir:
        pdf_path = os.path.join(tmpdir, "input.pdf")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        prefix = os.path.join(tmpdir, "page")
        try:
            subprocess.run(
                [exe, "-png", "-r", str(dpi), "-l", str(MAX_PDF_PAGES), pdf_path, prefix],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            logger.error("pdftoppm timed out after %ss", timeout)
            raise PdfConversionError("The PDF took too long to process. Try a smaller file or fewer pages.")
        except subprocess.CalledProcessError as err:
            detail = (err.stderr or b"").decode("utf-8", "replace").strip()[:300]
            logger.error("pdftoppm failed (exit %s): %s", err.returncode, detail)
            raise PdfConversionError("This PDF could not be read. It may be damaged or password-protected.")

        pages = []
        for page_file in sorted(glob.glob(os.path.join(tmpdir, "page-*.png"))):
            with open(page_file, "rb") as pf:
                pages.append(pf.read())
    if not pages:
        logger.error("pdftoppm produced no pages")
        raise PdfConversionError("No pages could be extracted from this PDF.")
    return pages
