import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from collections import defaultdict

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(
    page_title="Ausschüsse Grevenbroich",
    page_icon="🏛️",
    layout="wide"
)

st.title("🏛️ Ausschüsse der Stadt Grevenbroich")
st.markdown("### Geschlechterverteilung (11. Wahlperiode 2025–2030)")

# -----------------------------
# FETCH MIT PAGINATION
# -----------------------------
@st.cache_data(ttl=3600)
def fetch_all(url):
    results = []

    while url:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        results.extend(data.get("data", []))
        url = data.get("links", {}).get("next")

    return results

# -----------------------------
# MEMBERSHIP INDEX (KERNLOGIK)
# -----------------------------
def build_membership_index(people):
    memberships_by_org = defaultdict(dict)

    for person in people:
        person_id = person.get("id")
        gender = person.get("gender", "unknown")

        memberships = person.get("membership", [])
        if not isinstance(memberships, list):
            memberships = [memberships]

        for m in memberships:
            if not isinstance(m, dict):
                continue

            # 👉 org kann dict oder string sein
            org = m.get("organization")
            if isinstance(org, dict):
                org_id = org.get("id")
            else:
                org_id = org

            if not org_id:
                continue

            start = m.get("startDate", "")

            existing = memberships_by_org[org_id].get(person_id)

            # 👉 nur neueste Membership behalten
            if not existing or start > existing.get("startDate", ""):
                memberships_by_org[org_id][person_id] = {
                    "gender": gender,
                    "startDate": start
                }

    return memberships_by_org


def count_members(org_id, membership_index):
    members = {'male': 0, 'female': 0, 'unknown': 0}

    persons = membership_index.get(org_id, {})

    for p in persons.values():
        gender = p["gender"]

        if gender in ['male', 'männlich', 'm']:
            members['male'] += 1
        elif gender in ['female', 'weiblich', 'f']:
            members['female'] += 1
        else:
            members['unknown'] += 1

    return members


# -----------------------------
# LOAD DATA
# -----------------------------
with st.spinner("Lade Daten..."):
    organizations = fetch_all("http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/organizations")
    people = fetch_all("http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/people")

st.success(f"✅ {len(organizations)} Organisationen | {len(people)} Personen geladen")

# -----------------------------
# BUILD INDEX
# -----------------------------
membership_index = build_membership_index(people)

# -----------------------------
# FILTER GREMIEN
# -----------------------------
committees = []

for org in organizations:
    name = org.get("name", "").lower()

    if any(k in name for k in ['ausschuss', 'rat', 'beirat']):
        committees.append(org)

# -----------------------------
# BUILD STATS
# -----------------------------
committee_stats = []

for org in committees:
    org_id = org.get("id")
    org_name = org.get("name")

    members = count_members(org_id, membership_index)
    total = sum(members.values())

    if total == 0:
        continue

    committee_stats.append({
        'Name': org_name,
        'Männer': members['male'],
        'Frauen': members['female'],
        'Unbekannt': members['unknown'],
        'Gesamt': total,
        'Frauenanteil %': round((members['female'] / total) * 100, 1)
    })

# -----------------------------
# DISPLAY
# -----------------------------
if committee_stats:

    df = pd.DataFrame(committee_stats).sort_values("Gesamt", ascending=False)

    col1, col2 = st.columns([2, 1])

    # -------- Chart --------
    with col1:
        st.subheader("📊 Geschlechterverteilung")

        fig = go.Figure()

        fig.add_bar(y=df['Name'], x=df['Männer'], name='Männer', orientation='h')
        fig.add_bar(y=df['Name'], x=df['Frauen'], name='Frauen', orientation='h')

        if df['Unbekannt'].sum() > 0:
            fig.add_bar(y=df['Name'], x=df['Unbekannt'], name='Unbekannt', orientation='h')

        fig.update_layout(
            barmode='stack',
            height=max(400, len(df) * 40),
            margin=dict(l=0, r=0, t=30, b=0)
        )

        st.plotly_chart(fig, use_container_width=True)

    # -------- Stats --------
    with col2:
        st.subheader("📈 Kennzahlen")

        total_members = df['Gesamt'].sum()
        total_women = df['Frauen'].sum()
        total_men = df['Männer'].sum()

        st.metric("Ausschüsse", len(df))
        st.metric("Mitglieder", total_members)
        st.metric("Frauenanteil", f"{(total_women/total_members)*100:.1f}%")

    # -------- Tabelle --------
    st.subheader("📋 Übersicht")

    st.dataframe(
        df[['Name', 'Männer', 'Frauen', 'Gesamt', 'Frauenanteil %']],
        use_container_width=True,
        hide_index=True
    )

else:
    st.warning("Keine Daten gefunden.")

    # Debug
    with st.expander("Debug"):
        st.write("Organisationen:", len(organizations))
        st.write("Personen:", len(people))
        st.write("Membership Index:", len(membership_index))
