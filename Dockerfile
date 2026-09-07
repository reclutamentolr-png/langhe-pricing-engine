FROM python:3.11-slim

WORKDIR /app

# 1. Installa le dipendenze di sistema necessarie per far girare Chromium su Linux
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 2. Copia le dipendenze Python e installale
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Installa i browser di Playwright e le relative dipendenze di sistema (corrispondenti alla versione pip installata)
RUN playwright install chromium
RUN playwright install-deps chromium

# 4. Copia tutto il codice della tua app
COPY . .

# 5. Esponi la porta di Streamlit
EXPOSE 8501

# 6. Comando di avvio
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]