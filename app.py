import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Konfiguration
st.set_page_config(
    page_title="Ausschüsse Grevenbroich",
    page_icon="🏛️",
    layout="wide"
)

st.title("🏛️ Ausschüsse der Stadt Grevenbroich")
st.markdown("### Übersicht der Ausschüsse und Geschlechterverteilung")
st.markdown("**11. Wahlperiode 2025-2030**")

TARGET_DATE = datetime.strptime("2026-10-23", "%Y-%m-%d")

# ---------------- API ----------------

@st.cache_data(ttl=3600)
def fetch_body():
    url = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/"
    return requests.get(url).json()

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

# ---------------- WAHLPERIODE ----------------

body = fetch_body()
legislative_terms = body.get("legislativeTerm", [])

TARGET_TERM_ID = None

for term in legislative_terms:
    if term.get("startDate", "").startswith("2025"):
        TARGET_TERM_ID = term.get("id")
        break

st.info(f"Verwendete Wahlperiode: {TARGET_TERM_ID}")

# ---------------- FILTER ----------------

def is_valid_membership(m):
    # 1. legislativeTerm (Primär)
    term = m.get("legislativeTerm")
    
    if term:
        if isinstance(term, list):
            return TARGET_TERM_ID in term
        return term == TARGET_TERM_ID
    
    # 2. Fallback Datum
    start = m.get("startDate")
    end = m.get("endDate")
    
    if start and datetime.fromisoformat(start[:10]) > TARGET_DATE:
        return False
    
    if end and datetime.fromisoformat(end[:10]) < TARGET_DATE:
        return False
    
    return True

# ---------------- DATEN LADEN ----------------

with st.spinner('Lade Daten...'):
    org_response = fetch_organizations()
    people_response = fetch_people()

organizations = extract_paginated_data(org_response)
people = extract_paginated_data(people_response)

st.success(f"Rohdaten: {len(organizations)} Organisationen, {len(people)} Personen")

# ---------------- PERSONEN FILTERN ----------------

filtered_people = []

for person in people:
    memberships = person.get("membership", [])
    
    if not isinstance(memberships, list):
        memberships = [memberships]
    
    valid_memberships = [
        m for m in memberships
        if isinstance(m, dict) and is_valid_membership(m)
    ]
    
    if valid_memberships:
        person["membership"] = valid_memberships
        filtered_people.append(person)

st.success(f"Gefilterte Personen (Wahlperiode): {len(filtered_people)}")

# ---------------- MITGLIEDER JE AUSSCHUSS ----------------

def get_organization_members(org_id, people_data):
    members = {'male': 0, 'female': 0, 'unknown': 0}
    
    for person in people_data:
        for membership in person.get("membership", []):
            if membership.get("organization") == org_id:
                
                gender = person.get('gender', 'unknown')
                
                if gender in ['male', 'männlich', 'm']:
                    members['male'] += 1
                elif gender in ['female', 'weiblich', 'f']:
                    members['female'] += 1
                else:
                    members['unknown'] += 1
                break
    
    return members

# ---------------- AUSWERTUNG ----------------

committee_stats = []

for org in organizations:
    org_name = org.get('name', 'Unbekannt')
    org_id = org.get('id', '')
    
    # Nur relevante Gremien
    if not any(k in org_name.lower() for k in ['ausschuss', 'rat', 'gremium', 'beirat', 'kommission']):
        continue
    
    members = get_organization_members(org_id, filtered_people)
    total = sum(members.values())
    
    # 👉 nur Gremien mit Mitgliedern
    if total > 0:
        committee_stats.append({
            'Name': org_name,
            'Männer': members['male'],
            'Frauen': members['female'],
            'Unbekannt': members['unknown'],
            'Gesamt': total,
            'Frauenanteil %': round((members['female'] / total) * 100, 1)
        })

# ---------------- OUTPUT ----------------

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
    
    st.subheader("📋 Übersicht")
    st.dataframe(df, use_container_width=True, hide_index=True)

else:
    st.warning("Keine Daten gefunden")

# ---------------- FOOTER ----------------

st.markdown("---")
st.markdown("*Datenquelle: OParl API Grevenbroich*")
