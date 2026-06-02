FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    TZ=Asia/Shanghai \
    DISPLAY=:99

WORKDIR /app

# Runtime libraries for Chrome/Chromium, Xvfb, fonts, and Playwright.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl tzdata gnupg wget unzip \
       xvfb xauth \
       fonts-liberation fonts-noto-cjk \
       libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 \
       libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libnspr4 \
       libnss3 libxcomposite1 libxdamage1 libxfixes3 \
       libxkbcommon0 libxrandr2 libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Keep Google Chrome available for the local/Xvfb browser mode.
RUN wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium \
    && python -m cloakbrowser install

COPY . .

RUN mkdir -p /app/data/screenshots /app/data/cookies \
    && chmod -R 777 /app/data

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "server.py"]
