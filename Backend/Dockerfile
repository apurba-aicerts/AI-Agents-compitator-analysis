# Use Python 3.11 slim image as base
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies for cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# This installs all packages, including python-jose with its crypto extra
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# IMPORTANT: The backend listens on port 8000 inside the container
EXPOSE 8090

# Run the FastAPI app on port 8000 inside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8090"]