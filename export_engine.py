import pandas as pd
import xlsxwriter
from fpdf import FPDF
from datetime import datetime
import re

def clean_text(text):
    """Pulisce il testo da caratteri non supportati dal font Helvetica di FPDF"""
    if not text:
        return ""
    text = str(text)
    
    # 1. Sostituzione caratteri speciali comuni di Airbnb/Booking (incluso il colpevole "⋅")
    text = text.replace('⋅', ' - ')  # Punto medio di Airbnb
    text = text.replace('•', ' - ')  # Bullet point
    text = text.replace('–', ' - ')  # En dash
    text = text.replace('—', ' - ')  # Em dash
    
    # 2. Sostituzione Emoji con testo descrittivo
    text = text.replace('🎉', '[EVENTO] ').replace('🔴', '[ALTO] ').replace('🟡', '[MEDIO] ').replace('🟢', '[BASSO] ')
    text = text.replace('✅', '[SI] ').replace('❌', '[NO] ').replace('🏆', '[TOP] ').replace('💰', '[EUR] ')
    text = text.replace('📊', '[GRAF] ').replace('📅', '[CAL] ').replace('📄', '[PDF] ').replace('🚀', '[GO] ')
    text = text.replace('💾', '[SAVE] ').replace('⚠️', '[WARN] ')
    
    # 3. Rimozione regex di qualsiasi altra emoji residua
    emoji_pattern = re.compile("[" 
        u"\U0001F600-\U0001F64F" 
        u"\U0001F300-\U0001F5FF" 
        u"\U0001F680-\U0001F6FF" 
        u"\U0001F1E0-\U0001F1FF" 
        u"\U00002702-\U000027B0" 
        u"\U000024C2-\U0001F251" 
    "]+", flags=re.UNICODE)
    text = emoji_pattern.sub(r'', text)
    
    # 4. Sostituzione lettere accentate e simboli valuta per compatibilità Helvetica
    text = text.replace('€', 'EUR ').replace('è', 'e').replace('é', 'e').replace('à', 'a').replace('ì', 'i')
    text = text.replace('ò', 'o').replace('ù', 'u').replace('°', ' gradi')
    text = text.replace('"', "'").replace('"', "'")
    
    return text

def export_excel(df_competitor, df_calendario, property_name, owner_name, filename):
    # FIX: Rimuoviamo la colonna 'Snippet' che supera il limite di 32.767 caratteri di Excel
    df_export = df_competitor.copy()
    if 'Snippet' in df_export.columns:
        df_export = df_export.drop(columns=['Snippet'])
        
    with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
        workbook = writer.book
        header_format = workbook.add_format({'bold': True, 'bg_color': '#2E86AB', 'font_color': 'white', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        similar_format = workbook.add_format({'bg_color': '#D4EDDA', 'border': 1})
        different_format = workbook.add_format({'bg_color': '#F8D7DA', 'border': 1})
        money_format = workbook.add_format({'num_format': 'EUR #,##0.00', 'border': 1})
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy', 'border': 1})
        
        # Foglio 1: Analisi Competitor
        df_export.to_excel(writer, sheet_name='Analisi Competitor', index=False, startrow=2)
        ws1 = writer.sheets['Analisi Competitor']
        ws1.merge_range('A1:G1', f"Report Analisi Mercato - {property_name}", workbook.add_format({'bold': True, 'font_size': 14}))
        ws1.write(1, 0, f"Proprietario: {owner_name}", workbook.add_format({'italic': True}))
        ws1.set_column('A:A', 15); ws1.set_column('B:B', 12); ws1.set_column('C:C', 40)
        ws1.set_column('D:D', 12); ws1.set_column('E:E', 12); ws1.set_column('F:F', 12); ws1.set_column('G:G', 15)
        
        for row_num in range(2, len(df_export) + 2):
            is_similar = df_export.iloc[row_num-2].get('is_similar', False) if row_num-2 < len(df_export) else False
            fmt = similar_format if is_similar else different_format
            for col_num in range(7):
                if row_num-2 < len(df_export):
                    ws1.write(row_num, col_num, df_export.iloc[row_num-2, col_num], fmt)
        
        # Foglio 2: Calendario Prezzi
        df_calendario.to_excel(writer, sheet_name='Calendario Prezzi', index=False, startrow=2)
        ws2 = writer.sheets['Calendario Prezzi']
        ws2.merge_range('A1:D1', f"Calendario Prezzi 6 Mesi - {property_name}", workbook.add_format({'bold': True, 'font_size': 14}))
        ws2.set_column('A:A', 15); ws2.set_column('B:B', 12); ws2.set_column('C:C', 15); ws2.set_column('D:D', 40)
        
        for row_num in range(2, len(df_calendario) + 2):
            if row_num-2 < len(df_calendario):
                ws2.write(row_num, 0, df_calendario.iloc[row_num-2, 0], date_format)
                ws2.write(row_num, 2, df_calendario.iloc[row_num-2, 2], money_format)
    return filename

def export_pdf(df_competitor, df_calendario, property_name, owner_name, avg_price, filename):
    pdf = FPDF('P', 'mm', 'A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(0, 15, 'Langhe Pricing Engine', 0, 1, 'C')
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 10, 'Report Analisi Mercato', 0, 1, 'C')
    pdf.ln(5)
    
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, f'Immobile: {clean_text(property_name)}', 0, 1)
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 8, f'Proprietario: {clean_text(owner_name)}', 0, 1)
    pdf.cell(0, 8, f'Data Report: {datetime.now().strftime("%d/%m/%Y")}', 0, 1)
    pdf.cell(0, 8, f'Prezzo Medio Mercato (competitor simili): EUR {avg_price:.2f}', 0, 1)
    pdf.ln(10)
    
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, 'Analisi Competitor', 0, 1)
    pdf.ln(2)
    
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(46, 134, 171)
    pdf.set_text_color(255, 255, 255)
    col_widths = [30, 25, 60, 20, 20, 20]
    headers = ['Comune', 'Piattaforma', 'Titolo', 'Prezzo', 'Valutazione', 'Recensioni']
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 8, header, 1, 0, 'C', True)
    pdf.ln()
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Helvetica', '', 8)
    for index, row in df_competitor.iterrows():
        is_similar = row.get('is_similar', False)
        pdf.set_fill_color(212, 237, 218) if is_similar else pdf.set_fill_color(248, 215, 218)
        pdf.cell(col_widths[0], 7, clean_text(str(row.get('Comune', '')))[:15], 1, 0, 'L', True)
        pdf.cell(col_widths[1], 7, clean_text(str(row.get('Piattaforma', '')))[:12], 1, 0, 'C', True)
        pdf.cell(col_widths[2], 7, clean_text(str(row.get('Titolo', '')))[:35], 1, 0, 'L', True)
        pdf.cell(col_widths[3], 7, f"EUR {row.get('Prezzo', 0):.2f}", 1, 0, 'R', True)
        pdf.cell(col_widths[4], 7, str(row.get('Valutazione', '')), 1, 0, 'C', True)
        pdf.cell(col_widths[5], 7, str(row.get('Recensioni', '')), 1, 0, 'C', True)
        pdf.ln()
    
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, 'Calendario Prezzi - Prossimi 6 Mesi', 0, 1)
    pdf.ln(2)
    
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(46, 134, 171)
    pdf.set_text_color(255, 255, 255)
    cal_widths = [30, 25, 25, 100]
    cal_headers = ['Data', 'Giorno', 'Prezzo', 'Motivazione']
    for i, header in enumerate(cal_headers):
        pdf.cell(cal_widths[i], 8, header, 1, 0, 'C', True)
    pdf.ln()
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Helvetica', '', 8)
    for index, row in df_calendario.iterrows():
        pdf.cell(cal_widths[0], 7, str(row.get('Data', '')), 1, 0, 'L')
        pdf.cell(cal_widths[1], 7, clean_text(str(row.get('Giorno', ''))), 1, 0, 'L')
        prezzo_key = 'Prezzo Consigliato (EUR)' if 'Prezzo Consigliato (EUR)' in row else 'Prezzo Consigliato (€)'
        pdf.cell(cal_widths[2], 7, f"EUR {row.get(prezzo_key, 0):.2f}", 1, 0, 'R')
        pdf.cell(cal_widths[3], 7, clean_text(str(row.get('Motivazione', '')))[:60], 1, 0, 'L')
        pdf.ln()
    
    pdf.output(filename)
    return filename