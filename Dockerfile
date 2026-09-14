FROM python:3.10-slim

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
ENV PIP_DEFAULT_TIMEOUT=1000
RUN pip install --no-cache-dir -r requirements.txt

# The application code will be mounted as a volume in dev mode,
# but we can also copy it here for production builds.
COPY . .

# Expose the API server and Web server ports
EXPOSE 5000 8000
