import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from collections import defaultdict
import time

# Konfiguration für mobile Ansicht
st.set_page_config(
    page_title="Grevenbroich Ratsinformationssystem",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS für bessere mobile Darstellung
st.markdown("""
    <style>
    .main {
        padding: 1rem;
    }
    table {
        font-size: 0.9rem;
    }
    @media (max-width: 768px) {
        .main {
            padding: 0.5rem;
        }
        table {
            font-size: 0.8rem;
        }
    }
    </style>
""", unsafe_allow_html=True)

# Basis-URLs
BASE_URL = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013"
PEOPLE_URL = f"{BASE_URL}/people"
ORG_URL = f"{BASE_URL}/organizations"

# Wahlperiode definieren
WAHLPERIODE_START = datetime(2025, 11, 1)
# Stichtag: Mitgliedschaften die vor diesem Datum enden, werden ausgefiltert
CUTOFF_DATE = datetime(2026, 1, 31)

@st.cache_data(ttl=3600)
def fetch_all_pages(base_url):
    """
    Holt alle Seiten einer OParl-Liste durch Folgen der 'next'-Links.
    WICHTIG: totalPages ist in dieser API nicht zuverlässig!
    """
    all_data = []
    current_url = base_url
    page_count = 0
    max_pages = 100  # Sicherheitslimit
    
    while current_url and page_count < max_pages:
        page_count += 1
        
        try:
            response = requests.get(current_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Daten sammeln
            if 'data' in data:
                all_data.extend(data['data'])
            
            # Nächste Seite via 'next'-Link
            links = data.get('links', {})
            next_url = links.get('next')
            
            if not next_url:
                # Keine weitere Seite vorhanden
                break
            
            current_url = next_url
            
            # Kurze Pause um Server nicht zu überlasten
            time.sleep(0.05)
            
        except Exception as e:
            st.error(f"Fehler beim Abrufen von Seite {page_count}: {e}")
            break
    
    return all_data

@st.cache_data(ttl=3600)
def fetch_single_object(url):
    """Holt ein einzelnes Objekt"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return None

def normalize_gender(gender):
    """Normalisiert Geschlechtsangaben"""
    if not gender or gender == "":
        return "Divers"
    elif gender.lower() in ["männlich", "male", "m"]:
        return "Männlich"
    elif gender.lower() in ["weiblich", "female", "w", "f"]:
        return "Weiblich"
    else:
        return "Divers"

def is_in_current_period(membership):
    """
    Prüft ob Mitgliedschaft aktuell aktiv ist (nach dem 31.01.2026).
    Eine Mitgliedschaft ist aktiv wenn:
    1. Sie kein endDate hat (=aktuell aktiv)
    2. Sie ein endDate nach dem 31.01.2026 hat (=noch nicht beendet)
    """
    end_date_str = membership.get('endDate')
    
    # Kein Enddatum = Mitgliedschaft ist aktiv
    if not end_date_str:
        return True
    
    try:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # Mitgliedschaft ist nur aktiv, wenn sie nach dem Cutoff-Datum endet
        return end_date > CUTOFF_DATE
    except:
        return False

def main():
    st.title("🏛️ Ratsinformationssystem Grevenbroich")
    st.subheader("Wahlperiode 2025-2030")
    
    # Info-Box zum Filter
    with st.expander("ℹ️ Filter-Information & Bekannte Probleme"):
        st.info(f"""
        **Gefilterte Daten:**
        - Wahlperiode beginnt: {WAHLPERIODE_START.strftime('%d.%m.%Y')}
        - Ausgeschlossen: Mitgliedschaften mit Enddatum bis einschließlich {CUTOFF_DATE.strftime('%d.%m.%Y')}
        - Angezeigt: Alle aktiven Mitgliedschaften (ohne Enddatum oder mit Enddatum nach {CUTOFF_DATE.strftime('%d.%m.%Y')})
        """)
        
        st.warning("""
        **⚠️ Bekannte Einschränkungen der OParl-API:**
        
        - Die OParl-Schnittstelle gibt bei `totalPages` einen falschen Wert an
        - Wir folgen daher den `next`-Links bis zum Ende
        - Einige Gremien aus dem Ratsinformationssystem fehlen in der OParl-API
        - Dies ist ein Problem der Datensynchronisation beim Anbieter ITK Rheinland
        
        Bei Unstimmigkeiten wenden Sie sich bitte an ITK Rheinland.
        """)
    
    with st.spinner("Lade Daten von der OParl-API (alle Seiten werden durchlaufen)..."):
        # Progress-Anzeige
        progress_text = st.empty()
        
        progress_text.text("📥 Lade alle Personen (folge 'next'-Links)...")
        people_data = fetch_all_pages(PEOPLE_URL)
        
        progress_text.text("📥 Lade alle Organisationen/Gremien...")
        organizations_data = fetch_all_pages(ORG_URL)
        
        progress_text.empty()
    
    if not people_data:
        st.error("❌ Keine Personen-Daten konnten geladen werden. Bitte später erneut versuchen.")
        return
    
    if not organizations_data:
        st.warning("⚠️ Keine Organisations-Daten konnten geladen werden.")
    
    # Deduplizierung (falls eine Person mehrfach vorkommt)
    unique_people = {}
    for person in people_data:
        person_id = person.get('id')
        if person_id and person_id not in unique_people:
            unique_people[person_id] = person
    
    people_data = list(unique_people.values())
    
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
    
    for person in people_data:
        gender = normalize_gender(person.get('gender', ''))
        person_name = person.get('name', 'Unbekannt')
        person_id = person.get('id', '')
        
        # Mitgliedschaften verarbeiten
        memberships = person.get('membership', [])
        has_current_membership = False
        
        for membership_ref in memberships:
            # Mitgliedschaft-Objekt abrufen
            if isinstance(membership_ref, str):
                membership = fetch_single_object(membership_ref)
            else:
                membership = membership_ref
            
            if not membership:
                continue
            
            # Prüfen ob Mitgliedschaft aktuell aktiv ist
            if not is_in_current_period(membership):
                continue
            
            has_current_membership = True
            
            org_id = membership.get('organization')
            if not org_id:
                continue
            
            # Prüfen ob Organisation in OParl vorhanden ist
            if org_id not in org_dict:
                missing_orgs.add(org_id)
                # Versuche wenigstens die ID anzuzeigen
                org_name = f"⚠️ Gremium nicht in OParl (ID: .../{org_id.split('/')[-1]})"
            else:
                organization = org_dict[org_id]
                org_name = organization.get('name', 'Unbekannt')
            
            role = membership.get('role', '-')
            voting_right = "Ja" if membership.get('votingRight', False) else "Nein"
            
            # Start- und Enddatum für Anzeige
            start_date = membership.get('startDate', '-')
            end_date = membership.get('endDate', 'Aktiv')
            
            people_list.append({
                'Name': person_name,
                'Geschlecht': gender,
                'Ausschuss': org_name,
                'Rolle': role,
                'Stimmrecht': voting_right,
                'Von': start_date,
                'Bis': end_date
            })
            
            # Statistik aktualisieren
            org_gender_count[org_name][gender] += 1
        
        # Gesamtstatistik nur wenn Person in aktueller Periode aktiv
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
            for org_id in sorted(missing_orgs):
                st.code(org_id)
    
    # Tab-Navigation
    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 Personen", 
        "🏢 Ausschüsse", 
        "📊 Geschlechterverteilung",
        "📈 Ausschuss-Analyse"
    ])
    
    # Tab 1: Personenliste
    with tab1:
        st.header("Personen im Rat")
        
        if people_list:
            df_people = pd.DataFrame(people_list)
            
            # Filter-Optionen
            col1, col2 = st.columns(2)
            with col1:
                gender_filter = st.multiselect(
                    "Geschlecht filtern:",
                    options=["Männlich", "Weiblich", "Divers"],
                    default=["Männlich", "Weiblich", "Divers"]
                )
            with col2:
                org_filter = st.multiselect(
                    "Ausschuss filtern:",
                    options=sorted(df_people['Ausschuss'].unique()),
                    default=[]
                )
            
            # Filter anwenden
            filtered_df = df_people[df_people['Geschlecht'].isin(gender_filter)]
            if org_filter:
                filtered_df = filtered_df[filtered_df['Ausschuss'].isin(org_filter)]
            
            # Sortierung
            sort_by = st.selectbox("Sortieren nach:", ["Name", "Ausschuss", "Geschlecht", "Von"])
            filtered_df = filtered_df.sort_values(sort_by)
            
            st.dataframe(
                filtered_df,
                use_container_width=True,
                hide_index=True
            )
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Anzahl Einträge", len(filtered_df))
            with col2:
                unique_people = filtered_df['Name'].nunique()
                st.metric("Einzigartige Personen", unique_people)
        else:
            st.info("Keine Personen für die aktuelle Wahlperiode gefunden.")
    
    # Tab 2: Ausschussliste
    with tab2:
        st.header("Ausschüsse")
        
        # Ausschüsse filtern (nur die mit Mitgliedern in aktueller Periode)
        active_orgs = [org for org in organizations_data 
                      if org.get('name') in org_gender_count]
        
        if active_orgs or missing_orgs:
            org_list = []
            
            # Existierende Gremien aus OParl
            for org in active_orgs:
                org_name = org.get('name', 'Unbekannt')
                org_type = org.get('organizationType', '-')
                classification = org.get('classification', '-')
                
                # Mitgliederanzahl aus Statistik
                total_members = sum(org_gender_count[org_name].values())
                
                org_list.append({
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
            
            st.dataframe(
                df_orgs,
                use_container_width=True,
                hide_index=True
            )
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Ausschüsse in OParl", len(active_orgs))
            with col2:
                st.metric("Fehlende Gremien", len(missing_orgs))
        else:
            st.info("Keine Ausschüsse gefunden.")
    
    # Tab 3: Geschlechterverteilung (Kreisdiagramm)
    with tab3:
        st.header("Geschlechterverteilung gesamt")
        
        if any(gender_count.values()):
            # Kreisdiagramm
            fig_pie = px.pie(
                values=list(gender_count.values()),
                names=list(gender_count.keys()),
                title="Verteilung nach Geschlecht",
                color_discrete_map={
                    'Männlich': '#3498db',
                    'Weiblich': '#e74c3c',
                    'Divers': '#95a5a6'
                }
            )
            
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(
                height=400,
                margin=dict(t=50, b=20, l=20, r=20)
            )
            
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # Zahlen
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Männlich", gender_count['Männlich'])
            with col2:
                st.metric("Weiblich", gender_count['Weiblich'])
            with col3:
                st.metric("Divers", gender_count['Divers'])
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
    
    # Tab 4: Ausschuss-Analyse (Balkendiagramm)
    with tab4:
        st.header("Geschlechterverteilung nach Ausschuss")
        
        if org_gender_count:
            # Daten für Balkendiagramm vorbereiten (nur Gremien in OParl)
            chart_data = []
            for org_name, counts in org_gender_count.items():
                # Fehlende Gremien ausschließen
                if org_name.startswith('⚠️'):
                    continue
                    
                total = counts['Männlich'] + counts['Weiblich'] + counts['Divers']
                chart_data.append({
                    'Ausschuss': org_name,
                    'Männlich': counts['Männlich'],
                    'Weiblich': counts['Weiblich'],
                    'Divers': counts['Divers'],
                    'Gesamt': total
                })
            
            if chart_data:
                df_chart = pd.DataFrame(chart_data)
                df_chart = df_chart.sort_values('Gesamt', ascending=False)
                
                # Balkendiagramm
                fig_bar = go.Figure()
                
                fig_bar.add_trace(go.Bar(
                    name='Männlich',
                    x=df_chart['Ausschuss'],
                    y=df_chart['Männlich'],
                    marker_color='#3498db'
                ))
                
                fig_bar.add_trace(go.Bar(
                    name='Weiblich',
                    x=df_chart['Ausschuss'],
                    y=df_chart['Weiblich'],
                    marker_color='#e74c3c'
                ))
                
                fig_bar.add_trace(go.Bar(
                    name='Divers',
                    x=df_chart['Ausschuss'],
                    y=df_chart['Divers'],
                    marker_color='#95a5a6'
                ))
                
                fig_bar.update_layout(
                    title='Geschlechterverteilung pro Ausschuss',
                    xaxis_title='Ausschuss',
                    yaxis_title='Anzahl Personen',
                    barmode='group',
                    height=500,
                    xaxis_tickangle=-45,
                    margin=dict(b=150)
                )
                
                st.plotly_chart(fig_bar, use_container_width=True)
                
                # Detailtabelle
                st.subheader("Detaillierte Aufschlüsselung")
                st.dataframe(
                    df_chart,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Keine Daten für Ausschuss-Analyse verfügbar.")
        else:
            st.info("Keine Daten für Ausschuss-Analyse verfügbar.")
    
    # Footer
    st.markdown("---")
    st.caption(f"""
    Datenquelle: OParl-API Grevenbroich (ITK Rheinland) | 
    Wahlperiode ab {WAHLPERIODE_START.strftime('%d.%m.%Y')} | 
    Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')} | 
    {len(people_data)} Personen geladen
    """)

if __name__ == "__main__":
    main()
