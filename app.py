import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from datetime import datetime, timedelta
import statistics
from scraper_engine import execute_search
from export_engine import export_excel, export_pdf, clean_text

# ==========================================
# 1. GESTIONE DATABASE (SQLite)
# ==========================================
def init_db():
    conn = sqlite3.connect("langhe_pricing.db", check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT, role TEXT, email TEXT, full_name TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS properties 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, airbnb_link TEXT, booking_link TEXT, 
                  base_price REAL, min_price REAL, max_price REAL, target_comuni TEXT,
                  my_rating REAL DEFAULT 5.0, my_reviews INTEGER DEFAULT 15, my_keywords INTEGER DEFAULT 30,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS researches 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, property_id INTEGER, created_at TEXT, platform TEXT, avg_market_price REAL,
                  FOREIGN KEY (property_id) REFERENCES properties (id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS competitors 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, research_id INTEGER, comune TEXT, platform TEXT, title TEXT, 
                  price REAL, rating REAL, reviews INTEGER, snippet TEXT, is_similar INTEGER,
                  FOREIGN KEY (research_id) REFERENCES researches (id))''')
    
    # NUOVA TABELLA: Gestione Comuni
    c.execute('''CREATE TABLE IF NOT EXISTS comuni 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  nome TEXT UNIQUE, 
                  attivo INTEGER DEFAULT 1, 
                  is_test INTEGER DEFAULT 0)''')
    
    # Inserisci admin di default
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if c.fetchone() is None:
        admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password_hash, role, email, full_name) VALUES (?, ?, ?, ?, ?)",
                  ('admin', admin_hash, 'admin', 'admin@langhepricing.it', 'Amministratore'))
    
    # Inserisci comuni di default se la tabella è vuota
    c.execute("SELECT COUNT(*) FROM comuni")
    if c.fetchone()[0] == 0:
        comuni_default = [
            ("Guarene", 1, 0),
            ("Alba", 1, 0),
            ("Barolo", 1, 0),
            ("La Morra", 1, 0),
            ("Neive", 1, 0)
        ]
        c.executemany("INSERT INTO comuni (nome, attivo, is_test) VALUES (?, ?, ?)", comuni_default)
    
    conn.commit()
    return conn

def check_password(username, password):
    conn = init_db()
    c = conn.cursor()
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT id, username, role, full_name FROM users WHERE username = ? AND password_hash = ?", (username, pwd_hash))
    user = c.fetchone()
    conn.close()
    return user

def add_user(username, password, email, full_name):
    conn = init_db()
    c = conn.cursor()
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        c.execute("INSERT INTO users (username, password_hash, role, email, full_name) VALUES (?, ?, ?, ?, ?)",
                  (username, pwd_hash, 'client', email, full_name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def add_property(user_id, name, airbnb_link, booking_link, base_price, min_price, max_price, target_comuni, my_rating, my_reviews, my_keywords):
    conn = init_db()
    c = conn.cursor()
    c.execute('''INSERT INTO properties 
                 (user_id, name, airbnb_link, booking_link, base_price, min_price, max_price, target_comuni, my_rating, my_reviews, my_keywords) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, name, airbnb_link, booking_link, base_price, min_price, max_price, target_comuni, my_rating, my_reviews, my_keywords))
    conn.commit()
    conn.close()

def get_user_properties(user_id):
    conn = init_db()
    df = pd.read_sql_query("SELECT * FROM properties WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df

def get_all_users():
    conn = init_db()
    df = pd.read_sql_query("SELECT id, username, email, full_name, role FROM users WHERE role = 'client'", conn)
    conn.close()
    return df

def save_research(property_id, platform, avg_price, competitors_data):
    conn = init_db()
    c = conn.cursor()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO researches (property_id, created_at, platform, avg_market_price) VALUES (?, ?, ?, ?)",
              (property_id, created_at, platform, avg_price))
    research_id = c.lastrowid
    
    for comp in competitors_data:
        c.execute('''INSERT INTO competitors 
                     (research_id, comune, platform, title, price, rating, reviews, snippet, is_similar) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (research_id, comp['Comune'], comp['Piattaforma'], comp['Titolo'], comp['Prezzo'], 
                   comp['Valutazione'], comp['Recensioni'], comp['Snippet'], 1 if comp.get('is_similar') else 0))
    conn.commit()
    conn.close()
    return research_id

def get_researches(property_id):
    conn = init_db()
    df = pd.read_sql_query("SELECT * FROM researches WHERE property_id = ? ORDER BY created_at DESC", conn, params=(property_id,))
    conn.close()
    return df

def get_competitors(research_id):
    conn = init_db()
    df = pd.read_sql_query("SELECT * FROM competitors WHERE research_id = ?", conn, params=(research_id,))
    conn.close()
    return df

# ==========================================
# NUOVE FUNZIONI: Gestione Comuni
# ==========================================
def get_comuni(attivi_only=True):
    """Recupera i comuni dal database"""
    conn = init_db()
    if attivi_only:
        df = pd.read_sql_query("SELECT * FROM comuni WHERE attivo = 1 ORDER BY nome", conn)
    else:
        df = pd.read_sql_query("SELECT * FROM comuni ORDER BY nome", conn)
    conn.close()
    return df

def add_comune(nome, attivo=1, is_test=0):
    """Aggiunge un nuovo comune"""
    conn = init_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO comuni (nome, attivo, is_test) VALUES (?, ?, ?)", (nome, attivo, is_test))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_comune(comune_id, attivo, is_test):
    """Aggiorna lo stato di un comune (attivo/test)"""
    conn = init_db()
    c = conn.cursor()
    c.execute("UPDATE comuni SET attivo = ?, is_test = ? WHERE id = ?", (attivo, is_test, comune_id))
    conn.commit()
    conn.close()

def delete_comune(comune_id):
    """Elimina un comune"""
    conn = init_db()
    c = conn.cursor()
    c.execute("DELETE FROM comuni WHERE id = ?", (comune_id,))
    conn.commit()
    conn.close()

# ==========================================
# 2. LOGICA DI CALCOLO
# ==========================================
def calcola_quality_score(voto, num_rev, keyword_punti):
    score = 0
    score += float(voto or 0) * 8
    num_rev = int(num_rev or 0)
    if num_rev >= 100: score += 30
    elif num_rev >= 50: score += 25
    elif num_rev >= 20: score += 20
    elif num_rev >= 10: score += 15
    else: score += 10
    score += int(keyword_punti or 0)
    return min(round(score, 1), 100)

def stima_keyword_punti(snippet):
    if not snippet: return 0
    snippet = str(snippet).lower()
    keywords = ["parcheggio", "parking", "vista", "terrazza", "balcone", "giardino", "condizionatore", "aria condizionata", "camere", "bagni"]
    return min(sum(5 for k in keywords if k in snippet), 30)

GIORNI_IT = {
    "Monday": "Lunedì", "Tuesday": "Martedì", "Wednesday": "Mercoledì",
    "Thursday": "Giovedì", "Friday": "Venerdì", "Saturday": "Sabato", "Sunday": "Domenica"
}

EVENTI_LANGHE = [
    {"nome": "Fiera Int. Tartufo Bianco Alba", "inizio": "2026-10-03", "fine": "2026-12-08", "molt": 2.5},
    {"nome": "Vinum Alba", "inizio": "2026-04-25", "fine": "2026-04-28", "molt": 1.8},
    {"nome": "Cioccolatò", "inizio": "2026-10-23", "fine": "2026-11-01", "molt": 1.6},
    {"nome": "Fiera del Vino (Barolo)", "inizio": "2026-06-19", "fine": "2026-06-22", "molt": 1.7},
    {"nome": "Collisioni (Barolo)", "inizio": "2026-07-10", "fine": "2026-07-14", "molt": 2.0},
    {"nome": "Fiera del Tartufo (Neive)", "inizio": "2026-11-14", "fine": "2026-11-22", "molt": 1.5},
    {"nome": "Natale nelle Langhe", "inizio": "2026-12-20", "fine": "2027-01-06", "molt": 1.8},
    {"nome": "Vendemmia", "inizio": "2026-09-12", "fine": "2026-09-27", "molt": 1.7}
]

def calcola_prezzo(data_str, prezzo_base, config):
    data = datetime.strptime(data_str, "%Y-%m-%d")
    mese = data.month
    giorno = data.weekday()

    for ev in config["eventi"]:
        if datetime.strptime(ev["inizio"], "%Y-%m-%d") <= data <= datetime.strptime(ev["fine"], "%Y-%m-%d"):
            return round(prezzo_base * ev["molt"], 2), f"🎉 {ev['nome']}"

    if mese in [1, 2, 11]: stag = "Inverno"
    elif mese in [3, 4, 5]: stag = "Primavera"
    elif mese in [6, 7, 8]: stag = "Estate"
    else: stag = "Autunno"

    prezzo = prezzo_base * config["stagionalita"][stag] * config["giorno_settimana"][giorno]
    prezzo = max(config["prezzo_minimo"], min(prezzo, config["prezzo_massimo"]))

    return round(prezzo, 2), f"{stag} - {'Weekend' if giorno >= 4 else 'Infrasettimanale'}"

# ==========================================
# 3. GESTIONE STATO E LOGIN
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.set_page_config(page_title="Login - Langhe Pricing Engine", page_icon="")
    st.title("🔐 Accesso Riservato")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Accedi", type="primary", use_container_width=True)
        if submitted:
            user = check_password(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.user_id = user[0]
                st.session_state.username = user[1]
                st.session_state.role = user[2]
                st.session_state.full_name = user[3]
                st.rerun()
            else:
                st.error("❌ Username o password non validi.")
    st.stop()

st.set_page_config(page_title="Langhe Pricing Engine", page_icon="", layout="wide")

st.sidebar.title(f"👤 {st.session_state.full_name}")
st.sidebar.markdown(f"Ruolo: **{st.session_state.role.capitalize()}**")
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Logout", type="secondary", use_container_width=True):
    st.session_state.logged_in = False
    st.rerun()

# ==========================================
# 4. DASHBOARD PRINCIPALE
# ==========================================
if st.session_state.role == 'admin':
    st.header("🛠️ Pannello di Amministrazione")
    tab_admin1, tab_admin2, tab_admin3 = st.tabs(["👥 Gestisci Clienti", "🏡 Assegna Immobili", " Gestisci Comuni"])
    
    with tab_admin1:
        st.subheader("Aggiungi Nuovo Cliente")
        with st.form("add_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("Username")
                new_email = st.text_input("Email")
            with col2:
                new_password = st.text_input("Password temporanea", type="password")
                new_full_name = st.text_input("Nome e Cognome / Ragione Sociale")
            if st.form_submit_button("✅ Crea Cliente", type="primary"):
                if new_username and new_password and new_full_name:
                    if add_user(new_username, new_password, new_email, new_full_name):
                        st.success(f"Cliente '{new_full_name}' creato!")
                    else: st.error("Username già esistente.")
        st.markdown("---")
        st.dataframe(get_all_users(), use_container_width=True, hide_index=True)

    with tab_admin2:
        st.subheader("Aggiungi un Immobile a un Cliente")
        df_users = get_all_users()
        if df_users.empty:
            st.warning("Crea prima un cliente.")
            st.stop()
        with st.form("add_property_form"):
            selected_user = st.selectbox("Seleziona Cliente", df_users['full_name'].tolist())
            user_id = int(df_users[df_users['full_name'] == selected_user]['id'].values[0])
            
            prop_name = st.text_input("Nome Immobile")
            col1, col2 = st.columns(2)
            with col1:
                airbnb_link = st.text_input("Link Airbnb")
                base_price = st.number_input("Prezzo Base (€)", value=150)
                min_price = st.number_input("Prezzo Minimo (€)", value=90)
            with col2:
                booking_link = st.text_input("Link Booking")
                max_price = st.number_input("Prezzo Massimo (€)", value=450)
            
            st.markdown("**Dati per il Quality Score dell'immobile:**")
            col3, col4, col5 = st.columns(3)
            with col3: my_rating = st.number_input("Tua Valutazione (0-5)", min_value=0.0, max_value=5.0, value=5.0)
            with col4: my_reviews = st.number_input("Tue Recensioni (n°)", min_value=0, value=15)
            with col5: my_keywords = st.number_input("Punti Servizi (0-30)", min_value=0, max_value=30, value=30)
            
            # Carica comuni attivi dal database per il multiselect
            df_comuni_attivi = get_comuni(attivi_only=True)
            comuni_list = df_comuni_attivi['nome'].tolist() if not df_comuni_attivi.empty else []
            
            target_comuni = st.multiselect("Comuni di confronto", comuni_list, default=comuni_list[:2] if len(comuni_list) >= 2 else comuni_list)
            
            if st.form_submit_button("💾 Salva Immobile", type="primary"):
                if prop_name:
                    add_property(user_id, prop_name, airbnb_link, booking_link, base_price, min_price, max_price, ", ".join(target_comuni), my_rating, my_reviews, my_keywords)
                    st.success(f"Immobile '{prop_name}' aggiunto!")

    # NUOVA TAB: Gestione Comuni
    with tab_admin3:
        st.subheader(" Gestione Comuni Disponibili")
        st.markdown("Da qui puoi aggiungere nuovi comuni, abilitarli/disabilitarli o impostarli come 'TEST' per far provare l'applicativo ai clienti in modo limitato.")
        
        # Form per aggiungere nuovo comune
        with st.form("add_comune_form"):
            col1, col2 = st.columns(2)
            with col1:
                nuovo_comune = st.text_input("Nome del nuovo comune (es. Monforte d'Alba)")
            with col2:
                is_test = st.checkbox("Imposta come comune TEST (solo per prove)")
            if st.form_submit_button("➕ Aggiungi Comune", type="primary"):
                if nuovo_comune:
                    if add_comune(nuovo_comune, attivo=1, is_test=1 if is_test else 0):
                        st.success(f"Comune '{nuovo_comune}' aggiunto!")
                        st.rerun()
                    else:
                        st.error("Comune già esistente.")
                else:
                    st.warning("Inserisci il nome del comune.")
        
        st.markdown("---")
        
        # Lista comuni esistenti
        df_comuni = get_comuni(attivi_only=False)
        if not df_comuni.empty:
            st.markdown("### Comuni Configurati")
            
            for index, row in df_comuni.iterrows():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    nome_comune = row['nome']
                    if row['is_test'] == 1:
                        st.markdown(f"**{nome_comune}** 🧪 *(TEST)*")
                    else:
                        st.markdown(f"**{nome_comune}**")
                
                with col2:
                    attivo = row['attivo'] == 1
                    nuovo_stato = st.toggle("Attivo", value=attivo, key=f"attivo_{row['id']}")
                    if nuovo_stato != attivo:
                        update_comune(row['id'], 1 if nuovo_stato else 0, row['is_test'])
                        st.rerun()
                
                with col3:
                    is_test = row['is_test'] == 1
                    nuovo_test = st.toggle("Test", value=is_test, key=f"test_{row['id']}")
                    if nuovo_test != is_test:
                        update_comune(row['id'], row['attivo'], 1 if nuovo_test else 0)
                        st.rerun()
                
                with col4:
                    if st.button("️", key=f"delete_{row['id']}"):
                        delete_comune(row['id'])
                        st.rerun()
                
                st.markdown("---")
        else:
            st.info("Nessun comune configurato. Aggiungi il primo comune usando il form sopra.")

elif st.session_state.role == 'client':
    st.header(f"🏡 Dashboard: Revenue Management")
    df_props = get_user_properties(st.session_state.user_id)
    
    if df_props.empty:
        st.info("⚠️ Nessun immobile assegnato. Contatta l'amministratore.")
    else:
        prop_options = {f"{row['name']} ({row['target_comuni']})": row for index, row in df_props.iterrows()}
        selected_prop_name = st.selectbox("Scegli il tuo appartamento", list(prop_options.keys()))
        selected_prop = prop_options[selected_prop_name]
        
        # Carica comuni attivi dal database (escludendo quelli di test per default)
        df_comuni_attivi = get_comuni(attivi_only=True)
        comuni_disponibili = df_comuni_attivi['nome'].tolist() if not df_comuni_attivi.empty else []
        comuni_non_test = df_comuni_attivi[df_comuni_attivi['is_test'] == 0]['nome'].tolist() if not df_comuni_attivi.empty else []
        comuni_test = df_comuni_attivi[df_comuni_attivi['is_test'] == 1]['nome'].tolist() if not df_comuni_attivi.empty else []
        
        st.sidebar.subheader("💰 Parametri Prezzo")
        prezzo_base = st.sidebar.number_input("Prezzo Base di Partenza (€)", min_value=50, max_value=500, value=int(selected_prop['base_price']))
        prezzo_min = st.sidebar.number_input("Prezzo Minimo Assoluto (€)", min_value=0, max_value=prezzo_base, value=int(selected_prop['min_price']))
        prezzo_max = st.sidebar.number_input("Prezzo Massimo Assoluto (€)", min_value=prezzo_base, max_value=1000, value=int(selected_prop['max_price']))
        tolleranza = st.sidebar.slider("Tolleranza Quality Score (punti)", min_value=10, max_value=40, value=25)
        
        config = {
            "prezzo_minimo": prezzo_min,
            "prezzo_massimo": prezzo_max,
            "stagionalita": {"Inverno": 0.75, "Primavera": 1.0, "Estate": 1.2, "Autunno": 1.3},
            "giorno_settimana": {0: 0.85, 1: 0.85, 2: 0.85, 3: 0.90, 4: 1.25, 5: 1.40, 6: 1.15},
            "eventi": EVENTI_LANGHE
        }
        
        tab_c1, tab_c2, tab_c3, tab_c4 = st.tabs(["🔍 Nuova Ricerca", "📊 Analisi per Comune", "📅 Calendario Prezzi (6 Mesi)", "🎉 Eventi Speciali"])
        
        with tab_c1:
            st.subheader(f"Analisi per: {selected_prop['name']}")
            col1, col2, col3 = st.columns(3)
            col1.metric("Prezzo Base", f"€{prezzo_base}")
            col2.metric("Range", f"€{prezzo_min} - €{prezzo_max}")
            col3.metric("Quality Score Tuo", f"{calcola_quality_score(selected_prop['my_rating'], selected_prop['my_reviews'], selected_prop['my_keywords'])}/100")
            
            st.markdown("---")
            st.markdown("### 🔍 Configura Nuova Ricerca")
            
            with st.form("new_search_form", clear_on_submit=False):
                comuni_default = [c.strip() for c in str(selected_prop['target_comuni']).split(',')]
                
                # Mostra solo comuni attivi NON di test di default
                comuni_search = st.multiselect(
                    "Comuni da analizzare", 
                    comuni_non_test,
                    default=[c for c in comuni_default if c in comuni_non_test]
                )
                
                # Se ci sono comuni TEST, aggiungi opzione per includerli
                if comuni_test:
                    st.caption(f"💡 Sono disponibili {len(comuni_test)} comune/i TEST: {', '.join(comuni_test)}")
                    includi_test = st.checkbox("Includi comuni TEST nella ricerca", value=False)
                    if includi_test:
                        comuni_search = st.multiselect(
                            "Comuni da analizzare (inclusi TEST)", 
                            comuni_disponibili,
                            default=[c for c in comuni_default if c in comuni_disponibili]
                        )
                
                piattaforma_search = st.selectbox("Piattaforma", ["Airbnb", "Booking", "Entrambe"])
                max_annunci = st.slider("Max annunci per comune", 5, 20, 10)
                
                submitted = st.form_submit_button("🚀 Avvia Ricerca e Calcolo", type="primary", use_container_width=True)
                
                if submitted:
                    if not comuni_search:
                        st.error("⚠️ Seleziona almeno un comune.")
                    else:
                        if 'last_research' in st.session_state:
                            del st.session_state['last_research']
                        if 'avg_price' in st.session_state:
                            del st.session_state['avg_price']
                        
                        with st.spinner(f" Ricerca in corso su {piattaforma_search} per {', '.join(comuni_search)}... (attendere 1-2 min)"):
                            try:
                                print(f"🚀 [DEBUG] Avvio scraping per {comuni_search} su {piattaforma_search}...")
                                raw_data = execute_search(comuni_search, piattaforma_search, max_annunci)
                                print(f"✅ [DEBUG] Scraping finito. Trovati {len(raw_data)} annunci.")

                                if raw_data:
                                    mio_score = calcola_quality_score(selected_prop['my_rating'], selected_prop['my_reviews'], selected_prop['my_keywords'])
                                    competitor_validi_prezzi = []
                                    
                                    for item in raw_data:
                                        comp_score = calcola_quality_score(item['Valutazione'], item['Recensioni'], stima_keyword_punti(item['Snippet']))
                                        item['is_similar'] = abs(comp_score - mio_score) <= tolleranza
                                        if item['is_similar']:
                                            competitor_validi_prezzi.append(item['Prezzo'])
                                    
                                    avg_price = statistics.mean(competitor_validi_prezzi) if competitor_validi_prezzi else prezzo_base
                                    save_research(selected_prop['id'], piattaforma_search, avg_price, raw_data)
                                    
                                    st.session_state['last_research'] = raw_data
                                    st.session_state['avg_price'] = avg_price
                                    st.session_state['last_comuni'] = comuni_search
                                    
                                    st.success(f"✅ Ricerca completata! Trovati **{len(raw_data)} competitor**. Prezzo medio mercato simile: **€{avg_price:.2f}**")
                                    
                                    df_results = pd.DataFrame(raw_data)
                                    df_display = df_results[['Comune', 'Piattaforma', 'Titolo', 'Prezzo', 'Valutazione', 'Recensioni', 'is_similar']].copy()
                                    df_display['is_similar'] = df_display['is_similar'].apply(lambda x: '✅ SIMILE' if x else '❌ DIVERSO')
                                    
                                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                                    st.info("👉 Ora clicca sulla tab **' Analisi per Comune'** per vedere i dettagli divisi per zona e scaricare i Report PDF/Excel.")
                                else:
                                    st.error("⚠️ Nessun dato estratto. Riprova tra qualche minuto.")
                            except Exception as e:
                                st.error(f"❌ Errore durante lo scraping: {e}")
                                import traceback
                                traceback.print_exc()

        with tab_c2:
            st.subheader("Analisi Competitor per Zona")
            if 'last_research' in st.session_state:
                df_results = pd.DataFrame(st.session_state['last_research'])
                avg_price = st.session_state['avg_price']
                comuni_attuali = st.session_state.get('last_comuni', [c.strip() for c in str(selected_prop['target_comuni']).split(',')])
            else:
                df_researches = get_researches(selected_prop['id'])
                if not df_researches.empty:
                    latest_research = df_researches.iloc[0]
                    df_results = get_competitors(latest_research['id'])
                    df_results = df_results.rename(columns={'comune': 'Comune', 'platform': 'Piattaforma', 'title': 'Titolo', 'price': 'Prezzo', 'rating': 'Valutazione', 'reviews': 'Recensioni', 'is_similar': 'is_similar'})
                    avg_price = latest_research['avg_market_price']
                    comuni_attuali = [c.strip() for c in str(selected_prop['target_comuni']).split(',')]
                else:
                    st.info("Nessuna ricerca disponibile. Avvia una nuova ricerca nella tab '🔍 Nuova Ricerca'.")
                    st.stop()
            
            mio_score = calcola_quality_score(selected_prop['my_rating'], selected_prop['my_reviews'], selected_prop['my_keywords'])
            col1, col2 = st.columns(2)
            col1.metric("Il Tuo Quality Score", f"{mio_score}/100", "🏆 Top 10%")
            col2.metric("Competitor Totali", len(df_results))
            
            for comune in comuni_attuali:
                df_comune = df_results[df_results['Comune'] == comune] if 'Comune' in df_results.columns else pd.DataFrame()
                if len(df_comune) == 0: continue
                
                st.subheader(f"📍 {comune} ({len(df_comune)} annunci)")
                dati_tabella, competitor_validi_prezzi = [], []
                
                for index, row in df_comune.iterrows():
                    row_dict = {
                        "voto_recensioni": float(row.get("Valutazione", 0) or 0),
                        "num_recensioni": int(row.get("Recensioni", 0) or 0),
                        "keyword_punti": stima_keyword_punti(row.get("Snippet", ""))
                    }
                    score_comp = calcola_quality_score(row_dict["voto_recensioni"], row_dict["num_recensioni"], row_dict["keyword_punti"])
                    diff = abs(score_comp - mio_score)
                    prezzo_val = float(row.get("Prezzo", 0) or 0)
                    is_similar = bool(row.get('is_similar', diff <= tolleranza))
                    
                    stato = "✅ SIMILE" if is_similar else f"❌ Diff: {diff}pt"
                    dati_tabella.append({
                        "Piattaforma": row.get("Piattaforma", "N/D"),
                        "Annuncio": str(row.get("Titolo", "N/D"))[:50],
                        "Score": score_comp,
                        "Valutazione": row.get("Valutazione", "N/D"),
                        "Recensioni": row_dict["num_recensioni"],
                        "Prezzo (€)": prezzo_val,
                        "Stato": stato
                    })
                    if is_similar and prezzo_val > 0:
                        competitor_validi_prezzi.append(prezzo_val)
                
                st.dataframe(pd.DataFrame(dati_tabella), use_container_width=True, hide_index=True)
                if competitor_validi_prezzi:
                    prezzo_medio = statistics.mean(competitor_validi_prezzi)
                    st.info(f"💰 **{comune}** - Prezzo medio competitor simili: **€{prezzo_medio:.2f}** ({len(competitor_validi_prezzi)} strutture)")
                else:
                    st.warning(f"️ **{comune}** - Nessun competitor con qualità simile trovata.")
                st.markdown("---")
            
            st.markdown("---")
            st.subheader("📥 Export Report Professionale")
            date_list = []
            for i in range(180):
                data_futura = datetime.now() + timedelta(days=i)
                data_str = data_futura.strftime("%Y-%m-%d")
                giorno_en = data_futura.strftime("%A")
                giorno_it = GIORNI_IT.get(giorno_en, giorno_en)
                prezzo, motivo = calcola_prezzo(data_str, prezzo_base, config)
                date_list.append({"Data": data_str, "Giorno": giorno_it, "Prezzo Consigliato (EUR)": prezzo, "Motivazione": clean_text(motivo)})
            df_calendario = pd.DataFrame(date_list)
            
            col1, col2 = st.columns(2)
            with col1:
                excel_file = f"Report_{selected_prop['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                export_excel(df_results, df_calendario, selected_prop['name'], st.session_state.full_name, excel_file)
                with open(excel_file, "rb") as file:
                    st.download_button(label="📊 Scarica Report Excel Formattato", data=file, file_name=excel_file, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            with col2:
                pdf_file = f"Report_{selected_prop['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                export_pdf(df_results, df_calendario, selected_prop['name'], st.session_state.full_name, avg_price, pdf_file)
                with open(pdf_file, "rb") as file:
                    st.download_button(label=" Scarica Report PDF (Formato A4)", data=file, file_name=pdf_file, mime="application/pdf", use_container_width=True)

        with tab_c3:
            st.header("Previsione Prezzi per i Prossimi 6 Mesi")
            st.markdown("Il calendario applica automaticamente stagionalità, weekend ed eventi speciali delle Langhe.")
            date_list = []
            for i in range(180):
                data_futura = datetime.now() + timedelta(days=i)
                data_str = data_futura.strftime("%Y-%m-%d")
                giorno_en = data_futura.strftime("%A")
                giorno_it = GIORNI_IT.get(giorno_en, giorno_en)
                prezzo, motivo = calcola_prezzo(data_str, prezzo_base, config)
                colore = "🔴" if any(ev['nome'] in motivo for ev in EVENTI_LANGHE) else ("" if "Weekend" in motivo else "")
                date_list.append({"Data": data_str, "Giorno": giorno_it, "Prezzo Consigliato (€)": prezzo, "Motivazione": f"{colore} {motivo}"})
            df_calendario = pd.DataFrame(date_list)
            col_filt1, col_filt2 = st.columns(2)
            with col_filt1:
                mostra_eventi = st.checkbox("Mostra solo giorni con Eventi Speciali", value=False)
            with col_filt2:
                mostra_weekend = st.checkbox("Mostra solo Weekend", value=False)
            df_visualizzato = df_calendario.copy()
            if mostra_eventi:
                df_visualizzato = df_visualizzato[df_visualizzato["Motivazione"].str.contains("🔴")]
            if mostra_weekend:
                df_visualizzato = df_visualizzato[df_visualizzato["Giorno"].isin(["Sabato", "Domenica"])]
            st.dataframe(df_visualizzato, use_container_width=True, height=600)

        with tab_c4:
            st.header("🎉 Calendario Eventi Speciali Langhe")
            st.markdown("Questi eventi causano picchi di domanda. Il sistema applica automaticamente un moltiplicatore al prezzo base.")
            eventi_df = pd.DataFrame(EVENTI_LANGHE)
            eventi_df.columns = ["Evento", "Data Inizio", "Data Fine", "Moltiplicatore Prezzo"]
            eventi_df["Moltiplicatore Prezzo"] = eventi_df["Moltiplicatore Prezzo"].apply(lambda x: f"x{x}")
            st.dataframe(eventi_df, use_container_width=True, height=400)
            st.info("💡 **Come funziona:** Quando una data cade in un periodo di evento, il sistema ignora la stagionalità normale e applica direttamente il moltiplicatore dell'evento al prezzo base.")