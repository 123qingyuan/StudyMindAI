# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run typecheck && npm run build

# RapidOCR 1.4.4 requires Python <3.13. Keep the Linux runtime separate.
FROM python:3.12-slim-bookworm AS python-deps
WORKDIR /build
COPY backend/requirements-linux.txt ./
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements-linux.txt && /opt/venv/bin/pip check

FROM python:3.12-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 fonts-dejavu-core ca-certificates && rm -rf /var/lib/apt/lists/*     && groupadd --gid 10001 studymind && useradd --uid 10001 --gid 10001 --create-home studymind     && mkdir -p /var/lib/studymind && chown 10001:10001 /var/lib/studymind
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1     STUDYMIND_BUNDLE_ROOT=/app STUDYMIND_DATA_DIR=/var/lib/studymind     EMBEDDING_MODE=keyword HOME=/home/studymind
WORKDIR /app/backend
COPY --from=python-deps /opt/venv /opt/venv
COPY backend/app/ /app/backend/app/
COPY scripts/seed_computer_library.py scripts/seed_multidisciplinary_library.py /app/scripts/
COPY deploy/linux/runtime_check.py deploy/linux/entrypoint.py /app/deploy/linux/
COPY data/question_bank_manifest.json /app/data/question_bank_manifest.json
COPY data/builtin/legacy-expansion-v1/ /app/data/builtin/legacy-expansion-v1/
COPY --from=frontend /build/frontend/dist/ /app/frontend/dist/
USER 10001:10001
# Exercise packaged OCR/ONNX on Linux, without downloading a model.
RUN python /app/deploy/linux/runtime_check.py --build
EXPOSE 8765
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=6 CMD python -c "import json,urllib.request; r=json.load(urllib.request.urlopen('http://127.0.0.1:8765/api/health',timeout=4)); assert r['status']=='ok' and r['database']=='sqlite'"
ENTRYPOINT ["python", "/app/deploy/linux/entrypoint.py"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1", "--no-proxy-headers"]
