FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python test and lint dependencies
RUN pip install --no-cache-dir pytest ruff

# Create and set working directory
WORKDIR /workspace

# Healthcheck: verify pytest is importable
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 -c "import pytest; print('ok')" || exit 1

# Keep container running indefinitely for exec access
CMD ["tail", "-f", "/dev/null"]
