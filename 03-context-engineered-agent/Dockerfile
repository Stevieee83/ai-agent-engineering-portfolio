# Example 3 - context-engineered travel agent (agent.py), served by server.py.
# Matches the local "agent" conda env (Python 3.12; all packages come from pip),
# so a slim Python image is used instead of Miniconda.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code, data, knowledge base, skills and the React front end
COPY *.py ./
COPY data/ ./data/
COPY knowledge_base/ ./knowledge_base/
COPY skills/ ./skills/
COPY frontend/ ./frontend/

# Run as a non-root user
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# server.py binds to 127.0.0.1 when run directly, which is unreachable from
# outside a container, so start uvicorn on 0.0.0.0. Render injects $PORT.
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
