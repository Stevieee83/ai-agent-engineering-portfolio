# Matches the local "agent" conda env (Python 3.12 + Faker).
# The env only uses pip packages, so a slim Python image is lighter than Miniconda.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py travel_provider.py supported_locations.json ./

# Run as a non-root user
RUN useradd --create-home appuser
USER appuser

CMD ["python", "agent.py"]
