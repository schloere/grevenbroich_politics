import streamlit as st
import requests
import json

st.title("🔍 OParl Paginierungs-Debug")

BASE_URL = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/people"

st.header("Test 1: Erste Seite analysieren")

if st.button("Erste Seite abrufen"):
    try:
        response = requests.get(BASE_URL, timeout=10)
        data = response.json()
        
        st.success(f"✅ Status Code: {response.status_code}")
        
        st.subheader("Pagination-Info:")
        pagination = data.get('pagination', {})
        st.json(pagination)
        
        st.subheader("Links:")
        links = data.get('links', {})
        st.json(links)
        
        st.subheader(f"Anzahl Personen auf dieser Seite:")
        st.write(len(data.get('data', [])))
        
        st.subheader("Erste 3 Personen (Namen):")
        for person in data.get('data', [])[:3]:
            st.write(f"- {person.get('name', 'Unbekannt')}")
        
        # In Session State speichern
        st.session_state['first_page'] = data
        
    except Exception as e:
        st.error(f"❌ Fehler: {e}")

st.header("Test 2: Manuelle Seiten testen")

if 'first_page' in st.session_state:
    pagination = st.session_state['first_page'].get('pagination', {})
    total_pages = pagination.get('totalPages', 1)
    
    st.write(f"Laut API gibt es **{total_pages}** Seiten")
    
    page_to_test = st.number_input("Welche Seite testen?", min_value=1, max_value=max(total_pages, 10), value=2)
    
    if st.button(f"Seite {page_to_test} abrufen"):
        # Teste verschiedene URL-Formate
        test_urls = [
            f"{BASE_URL}?page={page_to_test}",
            f"{BASE_URL}/?page={page_to_test}",
        ]
        
        for test_url in test_urls:
            st.subheader(f"Teste: {test_url}")
            try:
                response = requests.get(test_url, timeout=10)
                data = response.json()
                
                st.success(f"✅ Status: {response.status_code}")
                st.write(f"Anzahl Personen: {len(data.get('data', []))}")
                st.write(f"Current Page: {data.get('pagination', {}).get('currentPage')}")
                
                # Erste 3 Namen zeigen
                for person in data.get('data', [])[:3]:
                    st.write(f"- {person.get('name', 'Unbekannt')}")
                
                break  # Wenn erfolgreich, nicht weiter testen
                
            except Exception as e:
                st.error(f"❌ Fehler: {e}")

st.header("Test 3: 'next' Link folgen")

if st.button("Alle Seiten via 'next' durchlaufen"):
    all_people = []
    current_url = BASE_URL
    page_count = 0
    
    progress_bar = st.progress(0)
    status = st.empty()
    
    while current_url and page_count < 100:  # Sicherheit: max 100 Seiten
        page_count += 1
        status.text(f"Lade Seite {page_count}...")
        
        try:
            response = requests.get(current_url, timeout=10)
            data = response.json()
            
            all_people.extend(data.get('data', []))
            
            # Nächste URL
            next_url = data.get('links', {}).get('next')
            
            st.write(f"**Seite {page_count}:** {len(data.get('data', []))} Personen")
            st.write(f"Next URL: {next_url if next_url else 'KEINE'}")
            
            if not next_url:
                break
                
            current_url = next_url
            progress_bar.progress(min(page_count / 10, 1.0))
            
        except Exception as e:
            st.error(f"Fehler auf Seite {page_count}: {e}")
            break
    
    progress_bar.empty()
    status.empty()
    
    st.success(f"✅ Insgesamt {len(all_people)} Personen von {page_count} Seiten geladen")
    
    # Einzigartige Namen zählen
    unique_names = set(p.get('name', '') for p in all_people)
    st.metric("Einzigartige Personen", len(unique_names))

st.header("Test 4: Alle Seiten manuell durchlaufen")

if 'first_page' in st.session_state:
    pagination = st.session_state['first_page'].get('pagination', {})
    total_pages = pagination.get('totalPages', 1)
    
    if st.button(f"Alle {total_pages} Seiten manuell abrufen"):
        all_people = []
        
        progress_bar = st.progress(0)
        status = st.empty()
        
        for page in range(1, total_pages + 1):
            status.text(f"Lade Seite {page} von {total_pages}...")
            
            try:
                url = f"{BASE_URL}?page={page}"
                response = requests.get(url, timeout=10)
                data = response.json()
                
                page_people = data.get('data', [])
                all_people.extend(page_people)
                
                if page % 10 == 0 or page == total_pages:
                    st.write(f"Seite {page}: {len(page_people)} Personen")
                
                progress_bar.progress(page / total_pages)
                
            except Exception as e:
                st.error(f"Fehler auf Seite {page}: {e}")
        
        progress_bar.empty()
        status.empty()
        
        st.success(f"✅ Insgesamt {len(all_people)} Personen von {total_pages} Seiten geladen")
        
        # Einzigartige Namen
        unique_names = set(p.get('name', '') for p in all_people)
        st.metric("Einzigartige Personen", len(unique_names))
        
        # Speichern
        st.session_state['all_people_manual'] = all_people

st.header("Test 5: Vergleich")

if 'all_people_manual' in st.session_state:
    all_people = st.session_state['all_people_manual']
    
    st.subheader("Stichprobe: Namen auf verschiedenen Seiten")
    
    # Suche nach Stefan Meuser
    search_name = st.text_input("Person suchen (z.B. 'Stefan Meuser'):", "Stefan Meuser")
    
    if search_name:
        found = [p for p in all_people if search_name.lower() in p.get('name', '').lower()]
        
        if found:
            st.success(f"✅ {len(found)} Person(en) gefunden:")
            for person in found:
                st.write(f"- {person.get('name', 'Unbekannt')}")
                st.json(person)
        else:
            st.error(f"❌ '{search_name}' nicht gefunden!")
    
    # Export
    st.subheader("Alle Namen exportieren")
    if st.button("Namen als Liste anzeigen"):
        names = sorted(set(p.get('name', 'Unbekannt') for p in all_people))
        for i, name in enumerate(names, 1):
            st.text(f"{i}. {name}")
        
        # Download
        names_text = "\n".join(names)
        st.download_button(
            "📥 Namen als Textdatei herunterladen",
            names_text,
            "personen_namen.txt",
            "text/plain"
        )
