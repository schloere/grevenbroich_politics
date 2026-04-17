import plotly.graph_objects as go
from datetime import datetime
from collections import defaultdict
import time

# Konfiguration für mobile Ansicht
st.set_page_config(
@@ -46,57 +45,27 @@
CUTOFF_DATE = datetime(2026, 1, 31)

@st.cache_data(ttl=3600)
def fetch_all_pages_improved(base_url):
    """
    Holt alle Seiten einer OParl-Liste.
    Verwendet sowohl 'next'-Links als auch manuelle Paginierung über ?page= Parameter.
    """
def fetch_all_pages(url):
    """Holt alle Seiten einer OParl-Liste"""
all_data = []
    current_url = url

    # Erste Seite abrufen
    try:
        response = requests.get(base_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data:
            all_data.extend(data['data'])
        
        # Paginierungs-Info auslesen
        pagination = data.get('pagination', {})
        total_pages = pagination.get('totalPages', 1)
        
        # Wenn es nur eine Seite gibt, sind wir fertig
        if total_pages <= 1:
            return all_data
        
        # Durch alle weiteren Seiten iterieren
        for page_num in range(2, total_pages + 1):
            try:
                # URL mit page-Parameter konstruieren
                separator = '&' if '?' in base_url else '?'
                page_url = f"{base_url}{separator}page={page_num}"
                
                response = requests.get(page_url, timeout=10)
                response.raise_for_status()
                page_data = response.json()
                
                if 'data' in page_data:
                    all_data.extend(page_data['data'])
                
                # Kurze Pause um Server nicht zu überlasten
                time.sleep(0.1)
                
            except Exception as e:
                st.warning(f"Fehler beim Abrufen von Seite {page_num}: {e}")
                # Weiter versuchen trotz Fehler
                continue
        
        return all_data
        
    except Exception as e:
        st.error(f"Fehler beim ersten Abrufen von {base_url}: {e}")
        return []
    while current_url:
        try:
            response = requests.get(current_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data:
                all_data.extend(data['data'])
            
            # Nächste Seite holen (gemäß OParl-Spezifikation)
            current_url = data.get('links', {}).get('next')
        except Exception as e:
            st.error(f"Fehler beim Abrufen von {current_url}: {e}")
            break
    
    return all_data

@st.cache_data(ttl=3600)
def fetch_single_object(url):
@@ -106,6 +75,7 @@ def fetch_single_object(url):
response.raise_for_status()
return response.json()
except Exception as e:
        st.warning(f"Fehler beim Abrufen von {url}: {e}")
return None

def normalize_gender(gender):
@@ -136,6 +106,7 @@ def is_in_current_period(membership):
end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

# Mitgliedschaft ist nur aktiv, wenn sie nach dem Cutoff-Datum endet
        # (d.h. endDate muss nach dem 31.01.2026 sein)
return end_date > CUTOFF_DATE
except:
return False
@@ -145,56 +116,31 @@ def main():
st.subheader("Wahlperiode 2025-2030")

# Info-Box zum Filter
    with st.expander("ℹ️ Filter-Information & Bekannte Probleme"):
    with st.expander("ℹ️ Filter-Information"):
st.info(f"""
       **Gefilterte Daten:**
       - Wahlperiode beginnt: {WAHLPERIODE_START.strftime('%d.%m.%Y')}
       - Ausgeschlossen: Mitgliedschaften mit Enddatum bis einschließlich {CUTOFF_DATE.strftime('%d.%m.%Y')}
       - Angezeigt: Alle aktiven Mitgliedschaften (ohne Enddatum oder mit Enddatum nach {CUTOFF_DATE.strftime('%d.%m.%Y')})
       """)
        
        st.warning("""
        **⚠️ Bekannte Einschränkungen der OParl-API:**
        
        Die OParl-Schnittstelle von ITK Rheinland liefert möglicherweise nicht alle Daten aus:
        - Einige Gremien aus dem Ratsinformationssystem fehlen in der OParl-API
        - Dies ist ein Problem der Datensynchronisation beim Anbieter
        - Die hier angezeigten Daten entsprechen dem aktuellen Stand der OParl-API
        
        Bei Unstimmigkeiten wenden Sie sich bitte an ITK Rheinland.
        """)

    with st.spinner("Lade Daten von der OParl-API (kann einige Sekunden dauern)..."):
        # Progress-Anzeige
        progress_text = st.empty()
        
        progress_text.text("📥 Lade Personen...")
        people_data = fetch_all_pages_improved(PEOPLE_URL)
        
        progress_text.text("📥 Lade Organisationen/Gremien...")
        organizations_data = fetch_all_pages_improved(ORG_URL)
        
        progress_text.empty()
    with st.spinner("Lade Daten von der OParl-API..."):
        # Daten laden
        people_data = fetch_all_pages(PEOPLE_URL)
        organizations_data = fetch_all_pages(ORG_URL)

    if not people_data:
        st.error("❌ Keine Personen-Daten konnten geladen werden. Bitte später erneut versuchen.")
    if not people_data or not organizations_data:
        st.error("Fehler beim Laden der Daten. Bitte später erneut versuchen.")
return

    if not organizations_data:
        st.warning("⚠️ Keine Organisations-Daten konnten geladen werden.")
    
    # Statistik anzeigen
    st.success(f"✅ {len(people_data)} Personen und {len(organizations_data)} Gremien von der OParl-API geladen")
    
# Organisationen in Dictionary für schnellen Zugriff
org_dict = {org['id']: org for org in organizations_data}

# Personen verarbeiten
people_list = []
gender_count = {"Männlich": 0, "Weiblich": 0, "Divers": 0}
org_gender_count = defaultdict(lambda: {"Männlich": 0, "Weiblich": 0, "Divers": 0})
    person_counted = set()
    missing_orgs = set()  # Gremien die referenziert werden, aber nicht in org_dict sind
    person_counted = set()  # Um Personen nur einmal zu zählen

for person in people_data:
gender = normalize_gender(person.get('gender', ''))
@@ -225,14 +171,8 @@ def main():
if not org_id:
continue

            # Prüfen ob Organisation in OParl vorhanden ist
            if org_id not in org_dict:
                missing_orgs.add(org_id)
                org_name = f"⚠️ Gremium nicht in OParl (ID: {org_id.split('/')[-1]})"
            else:
                organization = org_dict[org_id]
                org_name = organization.get('name', 'Unbekannt')
            
            organization = org_dict.get(org_id, {})
            org_name = organization.get('name', 'Unbekannt')
role = membership.get('role', '-')
voting_right = "Ja" if membership.get('votingRight', False) else "Nein"

@@ -254,28 +194,17 @@ def main():
org_gender_count[org_name][gender] += 1

# Gesamtstatistik nur wenn Person in aktueller Periode aktiv
        # und noch nicht gezählt wurde
if has_current_membership and person_id not in person_counted:
gender_count[gender] += 1
person_counted.add(person_id)

    # Warnung bei fehlenden Gremien
    if missing_orgs:
        with st.expander(f"⚠️ {len(missing_orgs)} Gremium/Gremien werden referenziert, sind aber nicht in der OParl-API verfügbar"):
            st.warning("""
            Die folgenden Gremien werden in Mitgliedschaften referenziert, 
            existieren aber nicht in der OParl-Gremien-Liste. 
            Dies ist ein Datenproblem beim OParl-Anbieter (ITK Rheinland).
            """)
            for org_id in missing_orgs:
                st.code(org_id)
    
# Tab-Navigation
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
    tab1, tab2, tab3, tab4 = st.tabs([
"👥 Personen", 
"🏢 Ausschüsse", 
"📊 Geschlechterverteilung",
        "📈 Ausschuss-Analyse",
        "🔍 Debug-Info"
        "📈 Ausschuss-Analyse"
])

# Tab 1: Personenliste
@@ -305,10 +234,6 @@ def main():
if org_filter:
filtered_df = filtered_df[filtered_df['Ausschuss'].isin(org_filter)]

            # Sortierung
            sort_by = st.selectbox("Sortieren nach:", ["Name", "Ausschuss", "Geschlecht"])
            filtered_df = filtered_df.sort_values(sort_by)
            
st.dataframe(
filtered_df,
use_container_width=True,
@@ -332,10 +257,8 @@ def main():
active_orgs = [org for org in organizations_data 
if org.get('name') in org_gender_count]

        if active_orgs or missing_orgs:
        if active_orgs:
org_list = []
            
            # Existierende Gremien aus OParl
for org in active_orgs:
org_name = org.get('name', 'Unbekannt')
org_type = org.get('organizationType', '-')
@@ -348,28 +271,12 @@ def main():
'Name': org_name,
'Typ': org_type,
'Klassifikation': classification,
                    'Status': '✅ In OParl',
'Mitglieder (gesamt)': total_members,
'Männlich': org_gender_count[org_name]['Männlich'],
'Weiblich': org_gender_count[org_name]['Weiblich'],
'Divers': org_gender_count[org_name]['Divers']
})

            # Fehlende Gremien hinzufügen
            for org_name in org_gender_count.keys():
                if org_name.startswith('⚠️'):
                    total_members = sum(org_gender_count[org_name].values())
                    org_list.append({
                        'Name': org_name,
                        'Typ': 'Unbekannt',
                        'Klassifikation': 'Unbekannt',
                        'Status': '⚠️ Fehlt in OParl',
                        'Mitglieder (gesamt)': total_members,
                        'Männlich': org_gender_count[org_name]['Männlich'],
                        'Weiblich': org_gender_count[org_name]['Weiblich'],
                        'Divers': org_gender_count[org_name]['Divers']
                    })
            
df_orgs = pd.DataFrame(org_list)
df_orgs = df_orgs.sort_values('Mitglieder (gesamt)', ascending=False)

@@ -379,11 +286,7 @@ def main():
hide_index=True
)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Ausschüsse in OParl", len(active_orgs))
            with col2:
                st.metric("Fehlende Gremien", len(missing_orgs))
            st.metric("Anzahl Ausschüsse", len(df_orgs))
else:
st.info("Keine Ausschüsse gefunden.")

@@ -423,20 +326,6 @@ def main():
with col4:
total = sum(gender_count.values())
st.metric("Gesamt", total)
                
            # Prozentuale Verteilung
            if total > 0:
                st.subheader("Prozentuale Verteilung")
                col1, col2, col3 = st.columns(3)
                with col1:
                    pct = (gender_count['Männlich'] / total) * 100
                    st.info(f"Männlich: {pct:.1f}%")
                with col2:
                    pct = (gender_count['Weiblich'] / total) * 100
                    st.info(f"Weiblich: {pct:.1f}%")
                with col3:
                    pct = (gender_count['Divers'] / total) * 100
                    st.info(f"Divers: {pct:.1f}%")
else:
st.info("Keine Daten zur Geschlechterverteilung verfügbar.")

@@ -506,35 +395,9 @@ def main():
else:
st.info("Keine Daten für Ausschuss-Analyse verfügbar.")

    # Tab 5: Debug-Info
    with tab5:
        st.header("Debug-Informationen")
        
        st.subheader("API-Endpunkte")
        st.code(f"Personen: {PEOPLE_URL}")
        st.code(f"Gremien: {ORG_URL}")
        
        st.subheader("Geladene Daten")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Personen geladen", len(people_data))
        with col2:
            st.metric("Gremien geladen", len(organizations_data))
        
        if missing_orgs:
            st.subheader("⚠️ Fehlende Gremien in OParl")
            st.warning(f"{len(missing_orgs)} Gremien werden referenziert, sind aber nicht in der OParl-API vorhanden.")
            
            for org_id in missing_orgs:
                st.text(org_id)
        
        st.subheader("Beispiel: Erste 5 Personen (Rohdaten)")
        if people_data:
            st.json(people_data[:5])
    
# Footer
st.markdown("---")
    st.caption(f"Datenquelle: OParl-API Grevenbroich (ITK Rheinland) | Wahlperiode ab {WAHLPERIODE_START.strftime('%d.%m.%Y')} | Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    st.caption(f"Datenquelle: OParl-API Grevenbroich | Wahlperiode ab {WAHLPERIODE_START.strftime('%d.%m.%Y')} | Aktive Mitgliedschaften (kein Enddatum oder Enddatum nach {CUTOFF_DATE.strftime('%d.%m.%Y')})")

if __name__ == "__main__":
main()
