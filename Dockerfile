FROM python:3.11-slim

WORKDIR /app

# Install Docker CLI (so the bot can control Docker on the host)
RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Render provides a PORT env var, but our bot doesn't need it (webhook not used).
# However, we must keep the container alive – we'll run the bot directly.
CMD ["python", "main.py"]