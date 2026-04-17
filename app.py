import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime

st.set_page_config(page_title="OParl Debug-Tool", layout="wide")

st.title("🔍 OParl API Debug-Tool")

BASE_URL = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013"

def fetch_with_debug(url):
    """Holt Daten und zeigt Debug-Informationen"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json(), response.status_code, None
    except Exception as e:
        return None, None, str(e)

# Tab-Struktur
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Personen-Statistik",
    "🔍 Seiten-Durchlauf",
    "👤 Person suchen",
    "📋 Rohdaten-Export"
])

with tab1:
    st.header("Personen-Statistik")
    
    if st.button("Personen-Liste analysieren", key="analyze"):
        people_url = f"{BASE_URL}/people"
        all_people = []
        page_count = 0
        
        with st.spinner("Lade alle Personen..."):
            current_url = people_url
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            while current_url:
                page_count += 1
                status_text.text(f"Lade Seite {page_count}...")
                
                data, status, error = fetch_with_debug(current_url)
                
                if error:
                    st.error(f"Fehler auf Seite {page_count}: {error}")
                    break
                
                if data and 'data' in data:
                    all_people.extend(data['data'])
                    
                    # Pagination Info
                    pagination = data.get('pagination', {})
                    links = data.get('links', {})
                    
                    st.info(f"""
                    **Seite {page_count}:**
                    - Personen auf dieser Seite: {len(data['data'])}
                    - Gesamtzahl laut API: {pagination.get('totalElements', 'N/A')}
                    - Aktuelle Seite: {pagination.get('currentPage', 'N/A')}
                    - Gesamt-Seiten: {pagination.get('totalPages', 'N/A')}
                    """)
                    
                    # Nächste Seite
                    current_url = links.get('next')
                    
                    if not current_url:
                        st.success("✅ Alle Seiten durchlaufen!")
                        break
                    
                    progress = min(page_count / pagination.get('totalPages', page_count), 1.0)
                    progress_bar.progress(progress)
                else:
                    break
            
            progress_bar.empty()
            status_text.empty()
        
        # Statistiken
        st.success(f"**Gesamt geladen: {len(all_people)} Personen von {page_count} Seiten**")
        
        # Mitgliedschafts-Analyse
        total_memberships = 0
        people_with_memberships = 0
        people_without_memberships = 0
        
        for person in all_people:
            memberships = person.get('membership', [])
            if memberships:
                people_with_memberships += 1
                total_memberships += len(memberships)
            else:
                people_without_memberships += 1
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Personen gesamt", len(all_people))
        with col2:
            st.metric("Mit Mitgliedschaften", people_with_memberships)
        with col3:
            st.metric("Ohne Mitgliedschaften", people_without_memberships)
        
        st.metric("Mitgliedschaften gesamt", total_memberships)
        
        # Speichere in Session State für andere Tabs
        st.session_state['all_people'] = all_people

with tab2:
    st.header("Seiten-Durchlauf prüfen")
    
    if st.button("Alle Seiten einzeln anzeigen", key="pages"):
        people_url = f"{BASE_URL}/people"
        current_url = people_url
        page_num = 0
        
        while current_url:
            page_num += 1
            st.subheader(f"Seite {page_num}")
            
            data, status, error = fetch_with_debug(current_url)
            
            if error:
                st.error(f"❌ Fehler: {error}")
                break
            
            if data:
                with st.expander(f"Seite {page_num} Details", expanded=(page_num <= 2)):
                    st.json({
                        'pagination': data.get('pagination', {}),
                        'links': data.get('links', {}),
                        'anzahl_personen': len(data.get('data', []))
                    })
                    
                    # Namen auf dieser Seite
                    names = [p.get('name', 'Unbekannt') for p in data.get('data', [])]
                    st.write("**Personen auf dieser Seite:**")
                    st.write(", ".join(names[:10]) + ("..." if len(names) > 10 else ""))
                
                current_url = data.get('links', {}).get('next')
                
                if not current_url:
                    st.success(f"✅ Ende nach {page_num} Seiten erreicht")
                    break
            else:
                break

with tab3:
    st.header("Person in OParl suchen")
    
    search_name = st.text_input("Name der Person eingeben (z.B. 'Rebecca Borgwardt'):")
    
    if search_name and st.button("Suchen", key="search"):
        if 'all_people' not in st.session_state:
            st.warning("Bitte zuerst in Tab 1 die Personen-Liste laden!")
        else:
            all_people = st.session_state['all_people']
            found = False
            
            for person in all_people:
                name = person.get('name', '')
                if search_name.lower() in name.lower():
                    found = True
                    st.success(f"✅ Person gefunden: {name}")
                    
                    with st.expander("Vollständige Person-Daten", expanded=True):
                        st.json(person)
                    
                    # Mitgliedschaften analysieren
                    memberships = person.get('membership', [])
                    st.write(f"**Anzahl Mitgliedschaften: {len(memberships)}**")
                    
                    for i, membership in enumerate(memberships, 1):
                        with st.expander(f"Mitgliedschaft {i}"):
                            st.json(membership)
            
            if not found:
                st.error(f"❌ Person '{search_name}' nicht in OParl gefunden!")
                st.info("Mögliche Gründe: Person wurde noch nicht synchronisiert, Schreibweise unterscheidet sich, oder Person ist nicht über OParl verfügbar.")

with tab4:
    st.header("Rohdaten-Export")
    
    if st.button("Komplette Personen-Liste als JSON exportieren", key="export"):
        if 'all_people' not in st.session_state:
            st.warning("Bitte zuerst in Tab 1 die Personen-Liste laden!")
        else:
            all_people = st.session_state['all_people']
            
            # JSON Download
            json_str = json.dumps(all_people, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 JSON herunterladen",
                data=json_str,
                file_name=f"oparl_people_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
            
            # CSV Export (vereinfacht)
            people_simple = []
            for person in all_people:
                people_simple.append({
                    'ID': person.get('id', ''),
                    'Name': person.get('name', ''),
                    'Vorname': person.get('givenName', ''),
                    'Nachname': person.get('familyName', ''),
                    'Geschlecht': person.get('gender', ''),
                    'Anzahl_Mitgliedschaften': len(person.get('membership', []))
                })
            
            df = pd.DataFrame(people_simple)
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            
            st.download_button(
                label="📥 CSV herunterladen",
                data=csv,
                file_name=f"oparl_people_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
            st.dataframe(df, use_container_width=True)

# Seitenleiste mit Infos
with st.sidebar:
    st.header("ℹ️ Debugging-Tipps")
    
    st.markdown("""
    ### Mögliche Probleme:
    
    1. **Paginierung**: Nicht alle Seiten werden durchlaufen
    2. **Cache**: OParl-API liefert veraltete Daten
    3. **Sync-Verzögerung**: Session vs. OParl nicht synchron
    4. **Filter**: API filtert automatisch
    
    ### Nächste Schritte:
    
    1. Tab 1: Gesamtzahl prüfen
    2. Tab 2: Alle Seiten durchgehen
    3. Tab 3: Fehlende Personen suchen
    4. Tab 4: Daten exportieren und mit Excel vergleichen
    
    ### Kontakt zum Anbieter:
    
    Falls Personen fehlen, solltest du den ITK Rheinland kontaktieren:
    - OParl-Sync prüfen lassen
    - Cache invalidieren
    - Vollständigkeit bestätigen
    """)
    
    st.info("💡 **Tipp**: Exportiere die JSON-Datei und vergleiche die IDs mit deiner Session-Excel-Liste!")
