import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ---------------- CONFIG ----------------

st.set_page_config(page_title="Politik Dashboard", layout="wide")
st.title("🏛️ Politik Dashboard Grevenbroich")

TARGET_DATE = datetime.strptime("2025-10-23", "%Y-%m-%d")

# ---------------- API ----------------

@st.cache_data(ttl=3600)
def fetch_all_pages(url):
    data = []
    while url:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        js = r.json()
        data.extend(js.get("data", []))
        url = js.get("links", {}).get("next")
    return data

@st.cache_data(ttl=3600)
def load():
    base = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/"
    return {
        "orgs": fetch_all_pages(base + "organizations/"),
        "people": fetch_all_pages(base + "people/"),
        "memberships": fetch_all_pages(base + "memberships/")
    }

data = load()

orgs = {o["id"]: o for o in data["orgs"]}
people = {p["id"]: p for p in data["people"]}
memberships = data["memberships"]

# ---------------- FILTER ----------------

def is_active(m):
    try:
        if m.get("startDate") and datetime.fromisoformat(m["startDate"][:10]) > TARGET_DATE:
            return False
        if m.get("endDate") and datetime.fromisoformat(m["endDate"][:10]) < TARGET_DATE:
            return False
    except:
        pass
    return True

valid = [m for m in memberships if is_active(m) and m.get("person") and m.get("organization")]

st.metric("Aktive Memberships", len(valid))

# ---------------- INDEX ----------------

# org_id -> set(person_ids)
org_members = {}

# person_id -> set(org_ids)
person_orgs = {}

for m in valid:
    o = m["organization"]
    p = m["person"]
    
    org_members.setdefault(o, set()).add(p)
    person_orgs.setdefault(p, set()).add(o)

st.metric("Personen gesamt", len(person_orgs))

# ---------------- AUSSCHÜSSE ----------------

# 👉 Ausschuss = Organisation mit >1 Mitglied
committees = {
    oid: members
    for oid, members in org_members.items()
    if len(members) > 1
}

st.metric("Gremien erkannt", len(committees))

# ---------------- GENDER ----------------

def gender(p):
    g = people.get(p, {}).get("gender")
    if g == "male":
        return "male"
    if g == "female":
        return "female"
    return "unknown"

# ---------------- STATS ----------------

rows = []

for oid, members in committees.items():
    male = female = unknown = 0
    
    for p in members:
        g = gender(p)
        if g == "male":
            male += 1
        elif g == "female":
            female += 1
        else:
            unknown += 1
    
    total = len(members)
    
    rows.append({
        "Name": orgs.get(oid, {}).get("name", oid),
        "Gesamt": total,
        "Männer": male,
        "Frauen": female,
        "Unbekannt": unknown,
        "Frauenanteil %": round((female / total) * 100, 1) if total else 0
    })

df = pd.DataFrame(rows).sort_values("Gesamt", ascending=False)

# ---------------- FRAKTIONEN ----------------

def faction(m):
    fid = m.get("onBehalfOf")
    if not fid:
        return "Unabhängig"
    return orgs.get(fid, {}).get("shortName") or orgs.get(fid, {}).get("name") or "?"

power = {}

for m in valid:
    f = faction(m)
    power[f] = power.get(f, 0) + 1

df_power = pd.DataFrame([
    {"Fraktion": k, "Sitze": v}
    for k, v in power.items()
]).sort_values("Sitze", ascending=False)

# ---------------- UI ----------------

st.subheader("🏛️ Machtverhältnisse")

fig = go.Figure()
fig.add_bar(x=df_power["Fraktion"], y=df_power["Sitze"])
st.plotly_chart(fig, use_container_width=True)

# ---------------- AUSSCHÜSSE ----------------

st.subheader("📊 Gremien")

fig2 = go.Figure()
fig2.add_bar(name="Männer", y=df["Name"], x=df["Männer"], orientation="h")
fig2.add_bar(name="Frauen", y=df["Name"], x=df["Frauen"], orientation="h")
fig2.add_bar(name="Unbekannt", y=df["Name"], x=df["Unbekannt"], orientation="h")

fig2.update_layout(barmode="stack", height=600)

st.plotly_chart(fig2, use_container_width=True)

st.dataframe(df, use_container_width=True)

# ---------------- DETAIL ----------------

st.subheader("🔍 Detail")

selected = st.selectbox("Gremium", df["Name"])

oid = next(k for k,v in orgs.items() if v.get("name") == selected)

dist = {}

for m in valid:
    if m["organization"] != oid:
        continue
    
    f = faction(m)
    dist[f] = dist.get(f, 0) + 1

df_dist = pd.DataFrame([
    {"Fraktion": k, "Sitze": v}
    for k, v in dist.items()
]).sort_values("Sitze", ascending=False)

st.dataframe(df_dist, use_container_width=True)
