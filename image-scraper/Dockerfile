FROM node:20-bookworm-slim

WORKDIR /app

# Chromium for headless Botasaurus rendering.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    python3 \
    python3-pip \
    ca-certificates \
    fonts-liberation \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Python rendering, parsing, and image conversion dependencies.
COPY requirements.txt ./
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY package*.json ./
RUN npm ci --omit=dev

COPY . .

ENV NODE_ENV=production
ENV PORT=3001
ENV CHROME_BIN=/usr/bin/chromium
ENV PYTHON_BIN=/usr/bin/python3
ENV HOST=0.0.0.0
ENV IMAGE_CLEANUP_ENABLED=false
ENV AUTO_RESUME_RESTORED_JOBS=false

EXPOSE 3001

CMD ["node", "server.js"]
