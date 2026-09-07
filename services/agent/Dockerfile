FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

EXPOSE 8001
CMD ["uvicorn", "opspilot_agent.api:app", "--host", "0.0.0.0", "--port", "8001"]
