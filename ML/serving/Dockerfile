FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY ML/pyproject.toml ML/uv.lock ./ML/
RUN cd ML && uv sync --frozen --no-install-project

COPY ML/ ./ML/
COPY data/processed/ ./data/processed/
# STEP8 CronJob(ML/pipeline/cronjobs/structure_new_reviews.py)이 재사용하는
# 5축 구조화 프롬프트/Upstage 호출 로직 — data/src/llm_review는 별도 프로젝트라
# 전체를 복사하지 않고 필요한 두 파일만 가져온다.
COPY data/src/llm_review/prompt_builder.py data/src/llm_review/structure_reviews.py ./data/src/llm_review/

EXPOSE 8001

CMD ["uv", "run", "--project", "ML", "uvicorn", "ML.serving.main:app", "--host", "0.0.0.0", "--port", "8001"]
