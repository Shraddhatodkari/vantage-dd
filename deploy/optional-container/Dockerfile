# ---- build the dashboard ----
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- API + static dashboard (single image) ----
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MLFLOW_DISABLE_AGENT_HINT=1
WORKDIR /app
RUN useradd --create-home --uid 10001 vantage
COPY backend/requirements.txt backend/requirements-postgres.txt backend/
RUN pip install --no-cache-dir -r backend/requirements-postgres.txt
COPY backend/ backend/
COPY data/ data/
COPY ml/artifacts/ ml/artifacts/
COPY --from=web /web/dist frontend/dist
RUN chown -R vantage /app
USER vantage
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/healthz')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
