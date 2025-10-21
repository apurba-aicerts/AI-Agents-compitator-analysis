# Use official Python slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Avoid buffering
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Expose Streamlit port
EXPOSE 8091

# Set default command
CMD ["streamlit", "run", "app.py", "--server.port=8091", "--server.address=0.0.0.0"]
