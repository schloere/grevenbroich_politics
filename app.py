import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from collections import defaultdict

# Konfiguration der Seite
st.set_page_config(
    page_title="Ausschüsse Grevenbroich",
    page_icon="🏛️",
    layout="wide"
)

# Titel und Beschreibung
st.title("🏛️ Ausschüsse der Stadt Grevenbroich")
st.markdown("### Übersicht der Ausschüsse und Geschlechterverteilung")
st.markdown("**11. Wahlperiode 2025-2030**")

# Caching für API-Aufrufe
@st.cache_data(ttl=3600)
def fetch_organizations():
    """Lade alle Organisationen (Ausschüsse) aus der API"""
    url = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/organizations"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Fehler beim Laden der Organisationen: {e}")
        return None

@st.cache_data(ttl=3600)
def fetch_people():
    """Lade alle Personen aus der API"""
    url = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/people"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Fehler beim Laden der Personen: {e}")
        return None

def extract_paginated_data(api_response):
    """Extrahiere Daten aus paginierten API-Antworten"""
    if not api_response:
        return []
    
    # Prüfe ob es eine paginierte Antwort ist
    if isinstance(api_response, dict) and 'data' in api_response:
        return api_response['data']
    elif isinstance(api_response, list):
        return api_response
    else:
        return []

def get_organization_members(org_id, people_data):
    """Ermittle alle Mitglieder einer Organisation mit Geschlecht"""
    members = {'male': 0, 'female': 0, 'unknown': 0}
    
    for person in people_data:
        if 'membership' in person:
            memberships = person['membership']
            if not isinstance(memberships, list):
                memberships = [memberships]
            
            for membership in memberships:
                # Prüfe ob die Person in dieser Organisation ist
                if isinstance(membership, dict):
                    member_org = membership.get('organization', '')
                elif isinstance(membership, str):
                    # Falls membership nur eine ID ist, lade die Details
                    continue
                else:
                    continue
                
                if member_org == org_id:
                    gender = person.get('gender', 'unknown')
                    if gender in ['male', 'männlich', 'm']:
                        members['male'] += 1
                    elif gender in ['female', 'weiblich', 'f']:
                        members['female'] += 1
                    else:
                        members['unknown'] += 1
                    break  # Person nur einmal zählen pro Organisation
    
    return members

# Lade Daten
with st.spinner('Lade Daten von der OParl-API...'):
    org_response = fetch_organizations()
    people_response = fetch_people()

if org_response and people_response:
    organizations = extract_paginated_data(org_response)
    people = extract_paginated_data(people_response)
    
    st.success(f"✅ {len(organizations)} Organisationen und {len(people)} Personen geladen")
    
    # Filtere nur Ausschüsse/Gremien der aktuellen Wahlperiode
    committees = []
    committee_stats = []
    
    for org in organizations:
        # Prüfe ob es ein relevantes Gremium ist
        org_type = org.get('organizationType', '')
        org_name = org.get('name', 'Unbekannt')
        org_id = org.get('id', '')
        
        # Filtere nach Ausschüssen, Räten, etc.
        if any(keyword in org_name.lower() for keyword in ['ausschuss', 'rat', 'gremium', 'beirat', 'kommission']):
            committees.append(org)
            
            # Ermittle Geschlechterverteilung
            members = get_organization_members(org_id, people)
            total = members['male'] + members['female'] + members['unknown']
            
            if total > 0:  # Nur Gremien mit Mitgliedern
                committee_stats.append({
                    'Name': org_name,
                    'Männer': members['male'],
                    'Frauen': members['female'],
                    'Unbekannt': members['unknown'],
                    'Gesamt': total,
                    'Frauenanteil %': round((members['female'] / total) * 100, 1) if total > 0 else 0
                })
    
    if committee_stats:
        df = pd.DataFrame(committee_stats)
        df = df.sort_values('Gesamt', ascending=False)
        
        # Layout: 2 Spalten
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📊 Geschlechterverteilung nach Ausschuss")
            
            # Gestapeltes Balkendiagramm
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                name='Männer',
                y=df['Name'],
                x=df['Männer'],
                orientation='h',
                marker_color='#4A90E2',
                text=df['Männer'],
                textposition='inside'
            ))
            
            fig.add_trace(go.Bar(
                name='Frauen',
                y=df['Name'],
                x=df['Frauen'],
                orientation='h',
                marker_color='#E94B8B',
                text=df['Frauen'],
                textposition='inside'
            ))
            
            if df['Unbekannt'].sum() > 0:
                fig.add_trace(go.Bar(
                    name='Unbekannt',
                    y=df['Name'],
                    x=df['Unbekannt'],
                    orientation='h',
                    marker_color='#CCCCCC',
                    text=df['Unbekannt'],
                    textposition='inside'
                ))
            
            fig.update_layout(
                barmode='stack',
                height=max(400, len(df) * 40),
                xaxis_title="Anzahl Mitglieder",
                yaxis_title="",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                margin=dict(l=0, r=0, t=30, b=0)
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("📈 Statistiken")
            
            total_members = df['Gesamt'].sum()
            total_women = df['Frauen'].sum()
            total_men = df['Männer'].sum()
            avg_women_percent = (total_women / total_members * 100) if total_members > 0 else 0
            
            st.metric("Gesamtanzahl Ausschüsse", len(df))
            st.metric("Gesamtanzahl Mitglieder", total_members)
            st.metric("Durchschnittlicher Frauenanteil", f"{avg_women_percent:.1f}%")
            
            # Kreisdiagramm Gesamtverteilung
            fig_pie = go.Figure(data=[go.Pie(
                labels=['Männer', 'Frauen'],
                values=[total_men, total_women],
                marker_colors=['#4A90E2', '#E94B8B'],
                hole=0.4
            )])
            
            fig_pie.update_layout(
                title="Gesamtverteilung",
                height=300,
                margin=dict(l=0, r=0, t=40, b=0)
            )
            
            st.plotly_chart(fig_pie, use_container_width=True)
        
        # Detaillierte Tabelle
        st.subheader("📋 Detaillierte Übersicht")
        
        # Formatiere die Tabelle
        df_display = df[['Name', 'Männer', 'Frauen', 'Gesamt', 'Frauenanteil %']].copy()
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Name": st.column_config.TextColumn("Ausschuss", width="large"),
                "Männer": st.column_config.NumberColumn("Männer", format="%d"),
                "Frauen": st.column_config.NumberColumn("Frauen", format="%d"),
                "Gesamt": st.column_config.NumberColumn("Gesamt", format="%d"),
                "Frauenanteil %": st.column_config.ProgressColumn(
                    "Frauenanteil",
                    format="%.1f%%",
                    min_value=0,
                    max_value=100
                )
            }
        )
        
        # Download-Button für CSV
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 Daten als CSV herunterladen",
            data=csv,
            file_name="ausschuesse_grevenbroich_2025-2030.csv",
            mime="text/csv"
        )
        
    else:
        st.warning("⚠️ Keine Ausschüsse mit Mitgliedern gefunden.")
        
        # Debug-Information
        with st.expander("🔍 Debug-Information anzeigen"):
            st.write("**Gefundene Organisationen:**")
            st.write(f"Anzahl: {len(organizations)}")
            if organizations:
                st.json(organizations[0])
            
            st.write("**Gefundene Personen:**")
            st.write(f"Anzahl: {len(people)}")
            if people:
                st.json(people[0])

else:
    st.error("❌ Fehler beim Laden der Daten. Bitte versuche es später erneut.")
    
# Footer
st.markdown("---")
st.markdown("*Datenquelle: OParl-API der Stadt Grevenbroich | 11. Wahlperiode 2025-2030*")
