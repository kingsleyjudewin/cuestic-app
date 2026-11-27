# Department Club OS Backend - Production Container (Render, Docker runtime)
#
#   docker build -t cuestic-api .
#   docker run --env-file .env.production -p 8080:8080 cuestic-api
#
# Secrets are NEVER baked in: .env and service-account JSON files are excluded by .dockerignore.
# On Render, mount the Firebase key as a Secret File (/etc/secrets/firebase-service-account.json).

# ---------- Stage 1: install Python dependencies into a virtualenv ----------
FROM python:3.12-slim AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# ---------- Stage 2: slim runtime ----------
FROM python:3.12-slim

# poppler-utils: pdftoppm (PDF -> images for OCR / reports)
# libgl1, libglib2.0-0: runtime libraries required by OpenCV (cv2, used by RapidOCR)
# fonts-dejavu-core: fonts for chart / image rendering
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils libgl1 libglib2.0-0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /home/app --create-home app

COPY --from=build /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_ENV=production \
    FLASK_APP=wsgi.py \
    PORT=8080 \
    TMPDIR=/tmp \
    MPLCONFIGDIR=/home/app/.cache/matplotlib \
    MPLBACKEND=Agg

WORKDIR /app

# Application code stays root-owned (read-only for the app user).
COPY . .

# Writable runtime directories only. Generated DOCX/charts are regenerable caches; persistent
# uploads must go to Firebase Storage or a mounted disk (STORAGE_LOCAL_ROOT).
RUN mkdir -p instance/storage instance/generated_reports instance/generated_charts \
             instance/generated_scripts uploads/research \
    && chown -R app:app instance uploads

USER app

# Build matplotlib's font cache now instead of on the first chart request.
RUN python -c "import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot" \
    && command -v pdftoppm >/dev/null

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=6s --start-period=40s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8080'), timeout=5)" || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
