FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --group app --no-install-project

COPY lick_finder ./lick_finder
COPY reports ./reports
COPY streamlit_app ./streamlit_app
COPY evals ./evals
RUN uv sync --frozen --no-dev --group app

# data/ is not baked in: lessons.json and the embeddings are gitignored and
# large. docker-compose mounts ./data here.
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
