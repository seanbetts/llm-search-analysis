# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (minimal - no Chrome needed)
RUN apt-get update && apt-get install -y \
  wget \
  && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
  pip install --no-cache-dir -r requirements.txt

# Note: Chrome runs natively on macOS host
# Playwright connects to it via CDP (Chrome DevTools Protocol)

# Copy application code
COPY app.py .
COPY .streamlit .streamlit
COPY src/ src/
COPY frontend/ frontend/

# Create data directory
RUN mkdir -p /app/data

# Expose port 8501 for Streamlit
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
