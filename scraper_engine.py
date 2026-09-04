import asyncio
import re
from playwright.async_api import async_playwright

async def scrape_airbnb(page, comune, max_annunci):
    url = f"https://www.airbnb.it/s/{comune}--Italy/homes?tab_id=home_tab&refinement_paths%5B%5D=%2Fhomes&query={comune.replace('-', '%20')},%20Italy"
    try:
        await page.goto(url, timeout=60000)
        try: await page.locator('button:has-text("Accetta tutto")').first.click(timeout=3000)
        except: pass
        
        await page.wait_for_selector('div[data-testid="listing-card-title"]', timeout=15000)
        listings = await page.locator('div[data-testid="listing-card-title"]').all()
        dati = []
        
        for listing in listings[:max_annunci]:
            try:
                titolo = await listing.inner_text()
                card = listing.locator('xpath=ancestor::div[contains(@class, "c1jz7u7")]').first
                if await card.count() == 0:
                    card = listing.locator('xpath=..').locator('xpath=..').locator('xpath=..').locator('xpath=..')
                card_text = await card.inner_text()
                
                prezzo = 0.0
                total_match = re.search(r'(\d+(?:[.,]\d{3})?)\s*(?:€|EUR)\s*in\s*totale', card_text, re.IGNORECASE)
                if total_match:
                    totale = float(total_match.group(1).replace(',', '.').replace('.', ''))
                    dates_match = re.search(r'(\d{1,2})\s*[–-]\s*(\d{1,2})', card_text)
                    if dates_match:
                        day_start, day_end = int(dates_match.group(1)), int(dates_match.group(2))
                        if day_end < day_start: day_end += 30
                        notti = day_end - day_start
                        if notti > 0: prezzo = totale / notti
                
                rating_match = re.search(r'([\d,]+)\s*su\s*5.*?\((\d+)\)', card_text)
                valutazione = float(rating_match.group(1).replace(',', '.')) if rating_match else 0.0
                num_recensioni = int(rating_match.group(2)) if rating_match else 0
                
                if prezzo > 0:
                    dati.append({"Comune": comune, "Piattaforma": "Airbnb", "Titolo": titolo.strip()[:60], 
                                 "Prezzo": round(prezzo, 2), "Valutazione": valutazione, "Recensioni": num_recensioni, "Snippet": card_text[:200].lower()})
            except: continue
        return dati
    except: return []

async def scrape_booking(page, comune, max_annunci):
    url = f"https://www.booking.com/searchresults.html?ss={comune}+Italy&checkin=2026-10-01&checkout=2026-10-03&group_adults=2&no_rooms=1"
    try:
        await page.goto(url, timeout=60000)
        try: await page.locator('button:has-text("Accetta")').first.click(timeout=3000)
        except: pass
        
        await page.wait_for_selector('div[data-testid="property-card"]', timeout=15000)
        cards = await page.locator('div[data-testid="property-card"]').all()
        dati = []
        
        for card in cards[:max_annunci]:
            try:
                card_text = await card.inner_text()
                titolo_match = re.search(r'^(.*?)(?:\||Si apre in una nuova finestra)', card_text, re.IGNORECASE | re.DOTALL)
                titolo = titolo_match.group(1).strip().replace('\n', ' ') if titolo_match else "Titolo non trovato"
                
                rating_match = re.search(r'([\d,]+)\s*(?:\|\s*)?(?:Eccezionale|Ottimo|Favoloso|Buono|Discreto)', card_text, re.IGNORECASE | re.DOTALL)
                valutazione = float(rating_match.group(1).replace(',', '.')) if rating_match else 0.0
                
                rev_match = re.search(r'(\d+)\s*recensioni', card_text, re.IGNORECASE)
                num_recensioni = int(rev_match.group(1)) if rev_match else 0
                
                price_match = re.search(r'(\d+)\s*notti.*?€\s*([\d,\.]+)', card_text, re.IGNORECASE | re.DOTALL)
                prezzo = 0.0
                if price_match:
                    notti = int(price_match.group(1))
                    totale = float(price_match.group(2).replace('.', '').replace(',', '.'))
                    if notti > 0: prezzo = totale / notti
                
                if prezzo > 0:
                    dati.append({"Comune": comune, "Piattaforma": "Booking", "Titolo": titolo[:60], 
                                 "Prezzo": round(prezzo, 2), "Valutazione": valutazione, "Recensioni": num_recensioni, "Snippet": card_text[:200].lower()})
            except: continue
        return dati
    except: return []

def execute_search(comuni, piattaforma, max_annunci=10):
    """Funzione principale chiamata da Streamlit"""
    async def _run():
        tutti_dati = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = await context.new_page()
            
            try:
                for comune in comuni:
                    if piattaforma in ["Airbnb", "Entrambe"]:
                        tutti_dati.extend(await scrape_airbnb(page, comune, max_annunci))
                        await asyncio.sleep(2)
                    if piattaforma in ["Booking", "Entrambe"]:
                        tutti_dati.extend(await scrape_booking(page, comune, max_annunci))
                        await asyncio.sleep(2)
            finally:
                await browser.close()
        return tutti_dati

    return asyncio.run(_run())