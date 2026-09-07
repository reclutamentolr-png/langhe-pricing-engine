FROM python:3.11-slim

WORKDIR /app

# 1. Aggiorna i pacchetti e installa curl (necessario per gli script di playwright)
RUN apt-get update && apt-get install -y curl

# 2. Copia e installa le dipendenze Python (incluso playwright)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Installa le dipendenze di sistema per Chromium (metodo moderno e supportato ufficialmente)
RUN playwright install-deps chromium

# 4. Scarica il browser Chromium corrispondente alla versione installata
RUN playwright install chromium

# 5. Copia tutto il codice della tua app
COPY . .

# 6. Esponi la porta di Streamlit
EXPOSE 8501

# 7. Comando di avvio
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]