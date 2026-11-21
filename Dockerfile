FROM python:3.15-slim

# Pinned, so builds are reproducible. Bump it deliberately (Dependabot opens the PR).
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /uvx /bin/
WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --group app --no-install-project

COPY lick_finder ./lick_finder
COPY reports ./reports
COPY streamlit_app ./streamlit_app
RUN uv sync --frozen --no-dev --group app

# data/ is not baked in: lessons.json and the embeddings are gitignored and
# large. docker-compose mounts ./data here. The app runs as an unprivileged
# user; it only needs to write to that mounted folder.
RUN useradd --create-home --uid 1000 app
USER app

ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)"]
CMD ["streamlit", "run", "streamlit_app/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
