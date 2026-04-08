FROM python:3.12-slim

WORKDIR /app

# (optional) system deps if your scraper needs them
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     ca-certificates curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Fly expects the app to listen on $PORT
ENV PORT=8080
EXPOSE 8080

# Gunicorn is production-ready; `app` must be the Flask object in app.py
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
