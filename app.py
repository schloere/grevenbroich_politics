import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Konfiguration der Seite
st.set_page_config(
    page_title="Ausschüsse Grevenbroich",
    page_icon="🏛️",
    layout="wide"
)

st.title("🏛️ Ausschüsse der Stadt Grevenbroich")
st.markdown("### Übersicht der Ausschüsse und Geschlechterverteilung")
st.markdown("**11. Wahlperiode 2025-2030**")

# 👉 Ziel-Wahlperiode (anpassen falls nötig)
TARGET_TERM = "2025"
TARGET_DATE = datetime.strptime("2026-10-23", "%Y-%m-%d")

# ---------------- API ----------------

@st.cache_data(ttl=3600)
def fetch_organizations():
    url = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/organizations/"
    return requests.get(url).json()

@st.cache_data(ttl=3600)
def fetch_people():
    url = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/people/"
    return requests.get(url).json()

def extract_paginated_data(api_response):
    if isinstance(api_response, dict) and 'data' in api_response:
        return api_response['data']
    return api_response or []

# ---------------- FILTER ----------------

def is_in_legislative_term(obj):
    """Filter über legislativeTerm (Primär)"""
    term = obj.get("legislativeTerm")
    
    if isinstance(term, str):
        return TARGET_TERM in term
    
    if isinstance(term, list):
        return any(TARGET_TERM in t for t in term)
    
    return False


def is_active_by_date(obj):
    """Fallback über Datum"""
    start = obj.get('startDate')
    end = obj.get('endDate')
    
    if start:
        if datetime.fromisoformat(start[:10]) > TARGET_DATE:
            return False
    
    if end:
        if datetime.fromisoformat(end[:10]) < TARGET_DATE:
            return False
    
    return True


def is_valid_organization(org):
    """Kombinierter Filter"""
    return is_in_legislative_term(org) or is_active_by_date(org)


def is_valid_membership(membership):
    """Membership-Filter"""
    return is_in_legislative_term(membership) or is_active_by_date(membership)

# ---------------- LOGIK ----------------

def get_organization_members(org_id, people_data):
    members = {'male': 0, 'female': 0, 'unknown': 0}
    
    for person in people_data:
        memberships = person.get('membership', [])
        
        if not isinstance(memberships, list):
            memberships = [memberships]
        
        for membership in memberships:
            if not isinstance(membership, dict):
                continue
            
            # 👉 Filter anwenden
            if not is_valid_membership(membership):
                continue
            
            if membership.get('organization') == org_id:
                gender = person.get('gender', 'unknown')
                
                if gender in ['male', 'männlich', 'm']:
                    members['male'] += 1
                elif gender in ['female', 'weiblich', 'f']:
                    members['female'] += 1
                else:
                    members['unknown'] += 1
                break
    
    return members

# ---------------- DATEN LADEN ----------------

with st.spinner('Lade Daten...'):
    org_response = fetch_organizations()
    people_response = fetch_people()

organizations = extract_paginated_data(org_response)
people = extract_paginated_data(people_response)

st.success(f"✅ {len(organizations)} Organisationen und {len(people)} Personen geladen")

# ---------------- AUSWERTUNG ----------------

committee_stats = []

for org in organizations:
    org_name = org.get('name', 'Unbekannt')
    org_id = org.get('id', '')
    
    # 👉 Nur gültige Gremien
    if not is_valid_organization(org):
        continue
    
    if any(k in org_name.lower() for k in ['ausschuss', 'rat', 'gremium', 'beirat', 'kommission']):
        
        members = get_organization_members(org_id, people)
        total = sum(members.values())
        
        if total > 0:
            committee_stats.append({
                'Name': org_name,
                'Männer': members['male'],
                'Frauen': members['female'],
                'Unbekannt': members['unknown'],
                'Gesamt': total,
                'Frauenanteil %': round((members['female'] / total) * 100, 1)
            })

# ---------------- VISUALISIERUNG ----------------

if committee_stats:
    df = pd.DataFrame(committee_stats).sort_values('Gesamt', ascending=False)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig = go.Figure()
        
        fig.add_bar(name='Männer', y=df['Name'], x=df['Männer'], orientation='h')
        fig.add_bar(name='Frauen', y=df['Name'], x=df['Frauen'], orientation='h')
        
        if df['Unbekannt'].sum() > 0:
            fig.add_bar(name='Unbekannt', y=df['Name'], x=df['Unbekannt'], orientation='h')
        
        fig.update_layout(barmode='stack')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        total_members = df['Gesamt'].sum()
        total_women = df['Frauen'].sum()
        
        st.metric("Ausschüsse", len(df))
        st.metric("Mitglieder", total_members)
        st.metric("Frauenanteil", f"{(total_women / total_members * 100):.1f}%")
    
    st.dataframe(df, use_container_width=True, hide_index=True)

else:
    st.warning("Keine Daten gefunden")

st.markdown("---")
st.markdown("*Datenquelle: OParl API Grevenbroich*")
