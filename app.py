import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from collections import defaultdict

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
def fetch_all_pages(url):
    """Holt alle Seiten einer OParl-Liste"""
    all_data = []
    current_url = url
    
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
    """Holt ein einzelnes Objekt"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.warning(f"Fehler beim Abrufen von {url}: {e}")
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
    Prüft ob Mitgliedschaft in der aktuellen Wahlperiode ist.
    Filtert Mitgliedschaften aus, die vor dem 01.02.2026 beendet wurden.
    """
    start_date_str = membership.get('startDate')
    end_date_str = membership.get('endDate')
    
    if not start_date_str:
        return False
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        
        # Wenn kein Enddatum angegeben, ist die Mitgliedschaft aktiv
        if not end_date_str:
            # Mitgliedschaft muss nach oder während der Wahlperiode begonnen haben
            return start_date >= WAHLPERIODE_START
        
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # Mitgliedschaft wird ausgefiltert, wenn sie vor dem Cutoff-Datum endet
        if end_date <= CUTOFF_DATE:
            return False
        
        # Mitgliedschaft muss die Wahlperiode überlappen
        return start_date >= WAHLPERIODE_START or end_date >= WAHLPERIODE_START
    except:
        return False

def main():
    st.title("🏛️ Ratsinformationssystem Grevenbroich")
    st.subheader("Wahlperiode 2025-2030")
    
    # Info-Box zum Filter
    with st.expander("ℹ️ Filter-Information"):
        st.info(f"""
        **Gefilterte Daten:**
        - Wahlperiode beginnt: {WAHLPERIODE_START.strftime('%d.%m.%Y')}
        - Ausgeschlossen: Mitgliedschaften mit Enddatum bis einschließlich {CUTOFF_DATE.strftime('%d.%m.%Y')}
        - Angezeigt: Nur aktive Mitgliedschaften ab {(CUTOFF_DATE + pd.Timedelta(days=1)).strftime('%d.%m.%Y')}
        """)
    
    with st.spinner("Lade Daten von der OParl-API..."):
        # Daten laden
        people_data = fetch_all_pages(PEOPLE_URL)
        organizations_data = fetch_all_pages(ORG_URL)
    
    if not people_data or not organizations_data:
        st.error("Fehler beim Laden der Daten. Bitte später erneut versuchen.")
        return
    
    # Organisationen in Dictionary für schnellen Zugriff
    org_dict = {org['id']: org for org in organizations_data}
    
    # Personen verarbeiten
    people_list = []
    gender_count = {"Männlich": 0, "Weiblich": 0, "Divers": 0}
    org_gender_count = defaultdict(lambda: {"Männlich": 0, "Weiblich": 0, "Divers": 0})
    person_counted = set()  # Um Personen nur einmal zu zählen
    
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
            
            # Prüfen ob in aktueller Wahlperiode (mit neuem Filter)
            if not is_in_current_period(membership):
                continue
            
            has_current_membership = True
            
            org_id = membership.get('organization')
            if not org_id:
                continue
            
            organization = org_dict.get(org_id, {})
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
        # und noch nicht gezählt wurde
        if has_current_membership and person_id not in person_counted:
            gender_count[gender] += 1
            person_counted.add(person_id)
    
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
        
        if active_orgs:
            org_list = []
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
            
            st.metric("Anzahl Ausschüsse", len(df_orgs))
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
        else:
            st.info("Keine Daten zur Geschlechterverteilung verfügbar.")
    
    # Tab 4: Ausschuss-Analyse (Balkendiagramm)
    with tab4:
        st.header("Geschlechterverteilung nach Ausschuss")
        
        if org_gender_count:
            # Daten für Balkendiagramm vorbereiten
            chart_data = []
            for org_name, counts in org_gender_count.items():
                total = counts['Männlich'] + counts['Weiblich'] + counts['Divers']
                chart_data.append({
                    'Ausschuss': org_name,
                    'Männlich': counts['Männlich'],
                    'Weiblich': counts['Weiblich'],
                    'Divers': counts['Divers'],
                    'Gesamt': total
                })
            
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
    
    # Footer
    st.markdown("---")
    st.caption(f"Datenquelle: OParl-API Grevenbroich | Wahlperiode ab {WAHLPERIODE_START.strftime('%d.%m.%Y')} | Aktive Mitgliedschaften ab {(CUTOFF_DATE + pd.Timedelta(days=1)).strftime('%d.%m.%Y')}")

if __name__ == "__main__":
    main()
