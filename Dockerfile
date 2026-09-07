FROM python:3.11-bullseye

WORKDIR /app

# 1. Aggiorna i pacchetti di sistema (bullseye è stabile e non ha il bug dei font mancanti)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Copia e installa le dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Installa Chromium e le sue dipendenze di sistema
# (Questo comando ora funzionerà perfettamente su bullseye)
RUN playwright install chromium
RUN playwright install-deps chromium

# 4. Copia tutto il codice della tua app
COPY . .

# 5. Esponi la porta di Streamlit
EXPOSE 8501

# 6. Comando di avvio
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]