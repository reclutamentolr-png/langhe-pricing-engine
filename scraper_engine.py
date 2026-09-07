import asyncio
import re
import requests
import os
from dotenv import load_dotenv
from datetime import datetime
import time
import random

# Carica le variabili d'ambiente
load_dotenv()

# Configura Zyte API
ZYTE_API_KEY = os.getenv("ZYTE_API_KEY")
ZYTE_API_URL = "https://api.zyte.com/v1/extract"

def scrape_with_zyte(url, wait_for_selector=None):
    """Esegue scraping usando Zyte API"""
    if not ZYTE_API_KEY:
        raise ValueError("ZYTE_API_KEY non trovata. Controlla il file .env")
    
    payload = {
        "url": url,
        "browserHtml": True,
        "actions": []
    }
    
    # Se serve aspettare un elemento specifico
    if wait_for_selector:
        payload["actions"].append({
            "action": "waitForSelector",
            "selector": wait_for_selector
        })
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {ZYTE_API_KEY}:",
    }
    
    try:
        response = requests.post(ZYTE_API_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result.get("browserHtml", "")
    except Exception as e:
        print(f"❌ Errore Zyte API: {e}")
        return ""

def parse_airbnb_results(html, comune, max_annunci):
    """Estrae i dati dall'HTML di Airbnb"""
    dati = []
    
    # Pattern per estrarre le card degli annunci
    # Nota: questi selettori potrebbero cambiare, monitorare
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    # Cerca tutti gli annunci (i selettori specifici di Airbnb)
    listings = soup.select('div[data-testid="listing-card"], div[class*="c1jz7u7"]')
    
    for listing in listings[:max_annunci]:
        try:
            # Estrai titolo
            titolo_elem = listing.select_one('[data-testid="listing-card-title"]')
            titolo = titolo_elem.get_text(strip=True) if titolo_elem else "Titolo non disponibile"
            
            # Estrai prezzo (cerca "in totale" o "notte")
            price_text = listing.get_text()
            prezzo = 0.0
            
            # Cerca prezzo totale e date
            total_match = re.search(r'(\d+(?:[.,]\d{3})?)\s*(?:€|EUR)\s*in\s*totale', price_text, re.IGNORECASE)
            if total_match:
                totale = float(total_match.group(1).replace(',', '.').replace('.', ''))
                dates_match = re.search(r'(\d{1,2})\s*[–-]\s*(\d{1,2})', price_text)
                if dates_match:
                    day_start = int(dates_match.group(1))
                    day_end = int(dates_match.group(2))
                    if day_end < day_start:
                        day_end += 30
                    notti = day_end - day_start
                    if notti > 0:
                        prezzo = totale / notti
            
            # Estrai valutazione e recensioni
            rating_match = re.search(r'([\d,]+)\s*su\s*5.*?\((\d+)\)', price_text)
            valutazione = float(rating_match.group(1).replace(',', '.')) if rating_match else 0.0
            num_recensioni = int(rating_match.group(2)) if rating_match else 0
            
            if prezzo > 0:
                dati.append({
                    "Comune": comune,
                    "Piattaforma": "Airbnb",
                    "Titolo": titolo[:60],
                    "Prezzo": round(prezzo, 2),
                    "Valutazione": valutazione,
                    "Recensioni": num_recensioni,
                    "Snippet": price_text[:200].lower()
                })
        except Exception as e:
            print(f"Errore parsing Airbnb: {e}")
            continue
    
    return dati

def parse_booking_results(html, comune, max_annunci):
    """Estrae i dati dall'HTML di Booking.com"""
    dati = []
    
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    # Cerca le card degli annunci
    cards = soup.select('div[data-testid="property-card"]')
    
    for card in cards[:max_annunci]:
        try:
            card_text = card.get_text()
            
            # Estrai titolo
            titolo_elem = card.select_one('div[data-testid="title"]')
            titolo = titolo_elem.get_text(strip=True) if titolo_elem else "Titolo non disponibile"
            
            # Estrai prezzo
            prezzo = 0.0
            price_match = re.search(r'(\d+)\s*notti.*?€\s*([\d,\.]+)', card_text, re.IGNORECASE)
            if price_match:
                notti = int(price_match.group(1))
                totale = float(price_match.group(2).replace('.', '').replace(',', '.'))
                if notti > 0:
                    prezzo = totale / notti
            
            # Estrai valutazione
            rating_match = re.search(r'([\d,]+)\s*(?:\|\s*)?(?:Eccezionale|Ottimo|Favoloso|Buono|Discreto)', card_text, re.IGNORECASE)
            valutazione = float(rating_match.group(1).replace(',', '.')) if rating_match else 0.0
            
            # Estrai recensioni
            rev_match = re.search(r'(\d+)\s*recensioni', card_text, re.IGNORECASE)
            num_recensioni = int(rev_match.group(1)) if rev_match else 0
            
            if prezzo > 0:
                dati.append({
                    "Comune": comune,
                    "Piattaforma": "Booking",
                    "Titolo": titolo[:60],
                    "Prezzo": round(prezzo, 2),
                    "Valutazione": valutazione,
                    "Recensioni": num_recensioni,
                    "Snippet": card_text[:200].lower()
                })
        except Exception as e:
            print(f"Errore parsing Booking: {e}")
            continue
    
    return dati

def execute_search(comuni, piattaforma, max_annunci=10):
    """Funzione principale che esegue la ricerca usando Zyte API"""
    print(f"🚀 Avvio scraping con Zyte API per: {comuni}")
    
    tutti_dati = []
    
    for comune in comuni:
        print(f"\n📍 Elaborazione {comune}...")
        
        if piattaforma in ["Airbnb", "Entrambe"]:
            print(f"  🔍 Airbnb: {comune}")
            url_airbnb = f"https://www.airbnb.it/s/{comune}--Italy/homes?tab_id=home_tab&refinement_paths%5B%5D=%2Fhomes&query={comune.replace('-', '%20')},%20Italy"
            
            html = scrape_with_zyte(url_airbnb, wait_for_selector='div[data-testid="listing-card-title"]')
            
            if html:
                dati_airbnb = parse_airbnb_results(html, comune, max_annunci)
                tutti_dati.extend(dati_airbnb)
                print(f"    ✅ Trovati {len(dati_airbnb)} annunci Airbnb")
            else:
                print(f"    ⚠️ Nessun dato estratto da Airbnb")
            
            time.sleep(random.uniform(2, 5))  # Pausa tra le richieste
        
        if piattaforma in ["Booking", "Entrambe"]:
            print(f"  🔍 Booking: {comune}")
            url_booking = f"https://www.booking.com/searchresults.html?ss={comune}+Italy&checkin=2026-10-01&checkout=2026-10-03&group_adults=2&no_rooms=1"
            
            html = scrape_with_zyte(url_booking, wait_for_selector='div[data-testid="property-card"]')
            
            if html:
                dati_booking = parse_booking_results(html, comune, max_annunci)
                tutti_dati.extend(dati_booking)
                print(f"    ✅ Trovati {len(dati_booking)} annunci Booking")
            else:
                print(f"    ⚠️ Nessun dato estratto da Booking")
            
            time.sleep(random.uniform(2, 5))
    
    print(f"\n📊 Totale annunci trovati: {len(tutti_dati)}")
    return tutti_dati