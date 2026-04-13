import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ---------------- CONFIG ----------------

st.set_page_config(
    page_title="Ausschüsse Grevenbroich",
    page_icon="🏛️",
    layout="wide"
)

st.title("🏛️ Ausschüsse der Stadt Grevenbroich")
st.markdown("### Übersicht der Ausschüsse und Geschlechterverteilung")
st.markdown("**11. Wahlperiode 2025-2030**")

TARGET_DATE = datetime.strptime("2025-10-23", "%Y-%m-%d")

# ---------------- API ----------------

@st.cache_data(ttl=3600)
def fetch_all_pages(url):
    all_data = []
    
    while url:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if "data" in result:
            all_data.extend(result["data"])
            url = result.get("links", {}).get("next")
        else:
            break
    
    return all_data

@st.cache_data(ttl=3600)
def fetch_organizations():
    return fetch_all_pages("http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/organizations/")

@st.cache_data(ttl=3600)
def fetch_people():
    return fetch_all_pages("http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/people/")

@st.cache_data(ttl=3600)
def fetch_memberships():
    return fetch_all_pages("http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/memberships/")

# ---------------- FILTER ----------------

def is_active_on_date(m):
    start = m.get("startDate")
    end = m.get("endDate")
    
    if start:
        try:
            if datetime.fromisoformat(start[:10]) > TARGET_DATE:
                return False
        except:
            pass
    
    if end:
        try:
            if datetime.fromisoformat(end[:10]) < TARGET_DATE:
                return False
        except:
            pass
    
    return True

# ---------------- LOAD ----------------

with st.spinner('Lade vollständige Daten (inkl. Memberships)...'):
    organizations = fetch_organizations()
    people = fetch_people()
    memberships = fetch_memberships()

st.success(f"Geladen: {len(organizations)} Organisationen, {len(people)} Personen, {len(memberships)} Memberships")

# ---------------- INDEXE ----------------

people_dict = {p["id"]: p for p in people}

# ---------------- MEMBERSHIPS FILTERN ----------------

valid_memberships = []
active_org_ids = set()
active_person_ids = set()

for m in memberships:
    if not isinstance(m, dict):
        continue
    
    if is_active_on_date(m):
        person_id = m.get("person")
        org_id = m.get("organization")
        
        if person_id and org_id:
            valid_memberships.append(m)
            active_person_ids.add(person_id)
            active_org_ids.add(org_id)

st.success(f"Aktive Memberships: {len(valid_memberships)}")
st.success(f"Eindeutige Personen: {len(active_person_ids)}")

# ---------------- MEMBERS PRO AUSSCHUSS ----------------

def get_organization_members(org_id):
    members = {'male': 0, 'female': 0, 'unknown': 0}
    seen = set()
    
    for m in valid_memberships:
        if m.get("organization") != org_id:
            continue
        
        person_id = m.get("person")
        
        if person_id in seen:
            continue
        
        seen.add(person_id)
        
        person = people_dict.get(person_id, {})
        gender = person.get("gender", "unknown")
        
        if gender in ['male', 'männlich', 'm']:
            members['male'] += 1
        elif gender in ['female', 'weiblich', 'f']:
            members['female'] += 1
        else:
            members['unknown'] += 1
    
    return members

# ---------------- AUSWERTUNG ----------------

committee_stats = []

for org in organizations:
    org_id = org.get("id")
    name = org.get("name", "")
    
    if org_id not in active_org_ids:
        continue
    
    if not any(k in name.lower() for k in ['ausschuss', 'rat', 'beirat', 'gremium', 'kommission']):
        continue
    
    members = get_organization_members(org_id)
    total = sum(members.values())
    
    if total > 0:
        committee_stats.append({
            'Name': name,
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
        st.metric("Ausschüsse", len(df))
        st.metric("Mitglieder", len(active_person_ids))
    
    st.subheader("📋 Übersicht")
    st.dataframe(df, use_container_width=True, hide_index=True)

else:
    st.warning("Keine Daten gefunden")

# ---------------- FOOTER ----------------

st.markdown("---")
st.markdown("*Datenquelle: OParl API Grevenbroich*")
