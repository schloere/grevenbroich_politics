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

TARGET_DATE = datetime.strptime("2026-10-23", "%Y-%m-%d")

# ---------------- API MIT PAGINATION ----------------

@st.cache_data(ttl=3600)
def fetch_all_pages(url):
    all_data = []
    
    while url:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if isinstance(result, dict) and "data" in result:
            all_data.extend(result["data"])
            url = result.get("links", {}).get("next")
        else:
            break
    
    return all_data

@st.cache_data(ttl=3600)
def fetch_organizations():
    url = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/organizations/"
    return fetch_all_pages(url)

@st.cache_data(ttl=3600)
def fetch_people():
    url = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/people/"
    return fetch_all_pages(url)

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

with st.spinner('Lade Daten vollständig (inkl. Pagination)...'):
    organizations = fetch_organizations()
    people = fetch_people()

st.success(f"Geladen: {len(organizations)} Organisationen, {len(people)} Personen")

# ---------------- PERSONEN FILTERN ----------------

filtered_people = []
active_org_ids = set()

for person in people:
    memberships = person.get("membership", [])
    
    if not isinstance(memberships, list):
        memberships = [memberships]
    
    valid_memberships = []
    
    for m in memberships:
        if not isinstance(m, dict):
            continue
        
        if is_active_on_date(m):
            valid_memberships.append(m)
            
            org_id = m.get("organization")
            if org_id:
                active_org_ids.add(org_id)
    
    if valid_memberships:
        person["membership"] = valid_memberships
        filtered_people.append(person)

st.success(f"Aktive Personen (Stichtag): {len(filtered_people)}")

# ---------------- MEMBERS ----------------

def get_organization_members(org_id, people_data):
    members = {'male': 0, 'female': 0, 'unknown': 0}
    
    for person in people_data:
        for m in person.get("membership", []):
            if m.get("organization") == org_id:
                
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
    org_id = org.get("id")
    org_name = org.get("name", "Unbekannt")
    
    if org_id not in active_org_ids:
        continue
    
    if not any(k in org_name.lower() for k in ['ausschuss', 'rat', 'beirat', 'gremium', 'kommission']):
        continue
    
    members = get_organization_members(org_id, filtered_people)
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

# ---------------- DEBUG ----------------

with st.expander("🔍 Debug"):
    st.write("Organisationen gesamt:", len(organizations))
    st.write("Personen gesamt:", len(people))
    st.write("Aktive Organisationen:", len(active_org_ids))

# ---------------- FOOTER ----------------

st.markdown("---")
st.markdown("*Datenquelle: OParl API Grevenbroich*")
