FROM python:3.14.7-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    chromium \
    curl \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Fly expects the app to listen on $PORT
ENV PORT=8080
EXPOSE 8080

# Keep one worker so the in-process automation scheduler cannot duplicate jobs.
# Use threads for concurrent requests and a long timeout for scraper workflows.
CMD ["sh", "-c", "gunicorn --workers ${WEB_WORKERS:-1} --threads ${WEB_THREADS:-8} --timeout ${WEB_TIMEOUT:-900} -b 0.0.0.0:${PORT:-8080} app:app"]
