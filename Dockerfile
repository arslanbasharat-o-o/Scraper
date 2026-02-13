FROM node:20-bookworm-slim

WORKDIR /app

# Chromium + matching chromedriver for selenium-webdriver.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    python3 \
    python3-pip \
    ca-certificates \
    fonts-liberation \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Python image conversion dependency used by convert_image.py
RUN python3 -m pip install --no-cache-dir --break-system-packages Pillow

COPY package*.json ./
RUN npm ci --omit=dev

COPY . .

ENV NODE_ENV=production
ENV PORT=3001
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV PYTHON_BIN=/usr/bin/python3
ENV CHROME_HEADLESS=true

EXPOSE 3001

CMD ["node", "server.js"]
