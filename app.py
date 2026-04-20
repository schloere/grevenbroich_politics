import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from collections import defaultdict
import time

st.set_page_config(
    page_title="Grevenbroich Ratsinformationssystem",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
.main { padding: 1rem; }
table { font-size: 0.9rem; }
@media (max-width: 768px) {
    .main { padding: 0.5rem; }
    table { font-size: 0.8rem; }
}
</style>
""", unsafe_allow_html=True)

BASE_URL = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013"
PEOPLE_URL = f"{BASE_URL}/people"
ORG_URL = f"{BASE_URL}/organizations"
PAPER_URL = f"{BASE_URL}/papers"
MEMBERSHIP_URL = f"{BASE_URL}/memberships"

WAHLPERIODE_START = datetime(2025, 11, 1)
CUTOFF_DATE = datetime(2026, 1, 31)


@st.cache_data(ttl=3600)
def fetch_all_pages(base_url, max_pages=200):
    all_data = []
    current_url = base_url
    page_count = 0

    while current_url and page_count < max_pages:
        page_count += 1
        try:
            response = requests.get(current_url, timeout=15)
            response.raise_for_status()
            data = response.json()

            if 'data' in data:
                all_data.extend(data['data'])

            current_url = data.get('links', {}).get('next')
            if not current_url:
                break

            time.sleep(0.05)

        except Exception as e:
            st.warning(f"Fehler bei {base_url}: {e}")
            break

    return all_data


@st.cache_data(ttl=3600)
def fetch_memberships():
    return fetch_all_pages(MEMBERSHIP_URL, max_pages=500)


def build_membership_index(memberships):
    index = defaultdict(list)
    for m in memberships:
        if m.get("person"):
            index[m["person"]].append(m)
    return index


def build_full_org_dict(orgs):
    org_dict = {o["id"]: o for o in orgs}

    added = True
    while added:
        added = False
        for org in list(org_dict.values()):
            parent = org.get("subOrganizationOf")
            if parent and parent not in org_dict:
                data = fetch_all_pages(parent, max_pages=1)
                if data:
                    org_dict[parent] = data[0]
                    added = True
    return org_dict


def normalize_gender(g):
    if not g:
        return "Divers"
    g = g.lower()
    if g in ["m", "male", "männlich"]:
        return "Männlich"
    if g in ["w", "f", "female", "weiblich"]:
        return "Weiblich"
    return "Divers"


def is_active(m):
    end = m.get("endDate")
    if not end:
        return True
    try:
        return datetime.strptime(end, "%Y-%m-%d") > CUTOFF_DATE
    except:
        return False


def get_party(person_id, membership_index, org_dict):
    for m in membership_index.get(person_id, []):
        if not is_active(m):
            continue
        org = org_dict.get(m.get("organization"))
        if not org:
            continue
        if org.get("organizationType", "").lower() in ["party", "fraction"]:
            return org.get("name")
    return None


def get_originators(paper):
    result = []
    for field in ["originatorPerson", "originatorOrganization", "creator"]:
        val = paper.get(field, [])
        if isinstance(val, str):
            val = [val]
        result.extend(val)
    return result


def main():
    st.title("🏛️ Ratsinformationssystem Grevenbroich")

    with st.spinner("Lade Daten..."):
        people = fetch_all_pages(PEOPLE_URL)
        orgs = fetch_all_pages(ORG_URL)
        papers = fetch_all_pages(PAPER_URL, 500)
        memberships = fetch_memberships()

    org_dict = build_full_org_dict(orgs)
    membership_index = build_membership_index(memberships)

    gender_count = defaultdict(int)
    org_gender = defaultdict(lambda: defaultdict(int))
    party_map = {}

    rows = []

    for p in people:
        pid = p["id"]
        name = p.get("name")
        gender = normalize_gender(p.get("gender"))

        party = get_party(pid, membership_index, org_dict)
        if party:
            party_map[pid] = party

        memberships = membership_index.get(pid, [])

        for m in memberships:
            if not is_active(m):
                continue

            org = org_dict.get(m.get("organization"))
            org_name = org.get("name") if org else "Unbekannt"

            rows.append({
                "Name": name,
                "Geschlecht": gender,
                "Partei": party,
                "Ausschuss": org_name
            })

            org_gender[org_name][gender] += 1

        gender_count[gender] += 1

    df = pd.DataFrame(rows)

    st.subheader("Personen")
    st.dataframe(df)

    st.subheader("Geschlecht gesamt")
    fig = px.pie(values=list(gender_count.values()), names=list(gender_count.keys()))
    st.plotly_chart(fig)

    st.subheader("Ausschüsse")
    org_df = pd.DataFrame([
        {
            "Ausschuss": k,
            "Männlich": v["Männlich"],
            "Weiblich": v["Weiblich"],
            "Divers": v["Divers"]
        }
        for k, v in org_gender.items()
    ])
    st.dataframe(org_df)

    st.subheader("Anträge nach Partei")

    stats = defaultdict(lambda: {"Anträge": 0, "Anfragen": 0, "Sonstige": 0})

    for p in papers:
        if p.get("date"):
            try:
                if datetime.strptime(p["date"], "%Y-%m-%d") < WAHLPERIODE_START:
                    continue
            except:
                pass

        t = p.get("paperType", "").lower()
        if "antrag" in t:
            cat = "Anträge"
        elif "anfrage" in t:
            cat = "Anfragen"
        else:
            cat = "Sonstige"

        for o in get_originators(p):
            if o in party_map:
                stats[party_map[o]][cat] += 1
            elif o in org_dict:
                org = org_dict[o]
                if org.get("organizationType", "").lower() in ["party", "fraction"]:
                    stats[org.get("name")][cat] += 1

    stats_df = pd.DataFrame([
        {
            "Partei": k,
            **v,
            "Gesamt": sum(v.values())
        }
        for k, v in stats.items()
    ]).sort_values("Gesamt", ascending=False)

    st.dataframe(stats_df)

    fig = go.Figure()
    fig.add_bar(name="Anträge", x=stats_df["Partei"], y=stats_df["Anträge"])
    fig.add_bar(name="Anfragen", x=stats_df["Partei"], y=stats_df["Anfragen"])
    fig.add_bar(name="Sonstige", x=stats_df["Partei"], y=stats_df["Sonstige"])
    fig.update_layout(barmode="stack")
    st.plotly_chart(fig)


if __name__ == "__main__":
    main()
