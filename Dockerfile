# Dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first (better build cache)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy bot code
COPY bot.py .

# Default command
CMD ["python", "bot.py"]
