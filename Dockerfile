FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    PYTHONPATH=/app \
    MODEL_NAME=gemini-3.7-flash \
    GOOGLE_CLOUD_PROJECT=elevate-taiwan-cohort-2 \
    GOOGLE_CLOUD_LOCATION=us-central1 \
    GOOGLE_API_USE_CLIENT_CERTIFICATE=false \
    GOOGLE_API_USE_MTLS_ENDPOINT=never

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source and static UI assets
COPY src/ ./src/
COPY static/ ./static/

# Expose HTTP port
EXPOSE 8080

# Run FastAPI app with Uvicorn
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8080"]
