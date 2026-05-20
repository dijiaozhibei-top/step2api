FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ src/
COPY pyproject.toml .
COPY config.example.json .

# Install the package
RUN pip install --no-cache-dir -e .

# Create data directory for persistent config
RUN mkdir -p /data && chmod 777 /data

ENV STEP2API_CONFIG_PATH=/data/config.json
ENV STEP2API_HOST=0.0.0.0
ENV STEP2API_PORT=5001

EXPOSE 5001

# Copy config if exists, otherwise use example
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "-m", "step2api.main"]
