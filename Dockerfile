# Usiamo l'immagine ufficiale Python di Playwright (include già Chromium e le librerie di sistema)
FROM mcr.microsoft.com/playwright/python:v1.38.0-jammy

# Imposta la cartella di lavoro
WORKDIR /app

# Copia le dipendenze Python e installale
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il codice della tua app
COPY . .

# Esponi la porta di Streamlit
EXPOSE 8501

# Comando di avvio
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]