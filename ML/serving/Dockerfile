FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY ML/pyproject.toml ML/uv.lock ./ML/
RUN cd ML && uv sync --frozen --no-install-project

COPY ML/ ./ML/
COPY data/processed/ ./data/processed/

EXPOSE 8001

CMD ["uv", "run", "--project", "ML", "uvicorn", "ML.serving.main:app", "--host", "0.0.0.0", "--port", "8001"]
