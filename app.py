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
st.markdown("### 11. Wahlperiode 2025–2030")

TARGET_DATE = datetime.strptime("2025-10-23", "%Y-%m-%d")

# ---------------- API ----------------

@st.cache_data(ttl=3600)
def fetch_all_pages(url):
    all_data = []
    while url:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        js = r.json()
        
        if "data" in js:
            all_data.extend(js["data"])
            url = js.get("links", {}).get("next")
        else:
            break
    return all_data

@st.cache_data(ttl=3600)
def load_data():
    base = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/"
    return (
        fetch_all_pages(base + "organizations/"),
        fetch_all_pages(base + "people/"),
        fetch_all_pages(base + "memberships/")
    )

with st.spinner("Lade Daten..."):
    organizations, people, memberships = load_data()

st.success(f"{len(organizations)} Organisationen | {len(people)} Personen | {len(memberships)} Memberships")

# ---------------- INDEX ----------------

org_dict = {o["id"]: o for o in organizations}
people_dict = {p["id"]: p for p in people}

# ---------------- FILTER ----------------

def is_active(m):
    start = m.get("startDate")
    end = m.get("endDate")
    
    try:
        if start and datetime.fromisoformat(start[:10]) > TARGET_DATE:
            return False
        if end and datetime.fromisoformat(end[:10]) < TARGET_DATE:
            return False
    except:
        pass
    
    return True

# ---------------- MEMBERSHIPS ----------------

valid_memberships = []

for m in memberships:
    if not isinstance(m, dict):
        continue
    
    # nur echte Mitglieder
    if m.get("role") not in ["member", "Mitglied"]:
        continue
    
    if not is_active(m):
        continue
    
    if m.get("person") and m.get("organization"):
        valid_memberships.append(m)

st.success(f"Aktive Memberships: {len(valid_memberships)}")

active_person_ids = set(m["person"] for m in valid_memberships)
st.metric("Mitglieder gesamt", len(active_person_ids))

# ---------------- GENDER ----------------

def infer_gender(person):
    g = person.get("gender")
    
    if g in ["male", "männlich", "m"]:
        return "male"
    if g in ["female", "weiblich", "f"]:
        return "female"
    
    name = person.get("name", "")
    
    if name.endswith(("a", "e")):
        return "female"
    
    return "unknown"

# ---------------- AUSSCHUSS FILTER ----------------

def is_committee(org):
    name = org.get("name", "").lower()
    
    keywords = [
        "ausschuss",
        "rat",
        "beirat",
        "kommission",
        "gremium"
    ]
    
    if any(k in name for k in keywords):
        return True
    
    if org.get("classification") == "committee":
        return True
    
    return False

# ---------------- MEMBERS PRO AUSSCHUSS ----------------

def get_members(org_id):
    members = {"male": 0, "female": 0, "unknown": 0}
    seen = set()
    
    for m in valid_memberships:
        if m["organization"] != org_id:
            continue
        
        pid = m["person"]
        
        if pid in seen:
            continue
        
        seen.add(pid)
        
        person = people_dict.get(pid, {})
        gender = infer_gender(person)
        
        members[gender] += 1
    
    return members

# ---------------- FRAKTIONEN ----------------

def get_fraction_name(fid):
    org = org_dict.get(fid, {})
    return org.get("shortName") or org.get("name") or "Unbekannt"

def get_committee_distribution(org_id):
    dist = {}
    seen = set()
    
    for m in valid_memberships:
        if m["organization"] != org_id:
            continue
        
        pid = m["person"]
        
        if pid in seen:
            continue
        
        seen.add(pid)
        
        frac = get_fraction_name(m.get("onBehalfOf"))
        dist[frac] = dist.get(frac, 0) + 1
    
    return dist

# ---------------- AUSSCHÜSSE ----------------

committee_stats = []

for org in organizations:
    if not is_committee(org):
        continue
    
    members = get_members(org["id"])
    total = sum(members.values())
    
    if total == 0:
        continue
    
    committee_stats.append({
        "Name": org["name"],
        "Männer": members["male"],
        "Frauen": members["female"],
        "Unbekannt": members["unknown"],
        "Gesamt": total,
        "Frauenanteil %": round(members["female"] / total * 100, 1)
    })

# 👉 Crash-Schutz
if not committee_stats:
    st.error("Keine Ausschüsse gefunden – Filter prüfen")
    st.stop()

df = pd.DataFrame(committee_stats).sort_values("Gesamt", ascending=False)

# ---------------- MACHTVERTEILUNG ----------------

power = {}

for m in valid_memberships:
    frac = get_fraction_name(m.get("onBehalfOf"))
    power[frac] = power.get(frac, 0) + 1

df_power = pd.DataFrame([
    {"Fraktion": k, "Sitze": v}
    for k, v in power.items()
]).sort_values("Sitze", ascending=False)

# ---------------- UI ----------------

st.subheader("🏛️ Machtverhältnisse")

fig_power = go.Figure()
fig_power.add_bar(x=df_power["Fraktion"], y=df_power["Sitze"])
fig_power.update_layout(height=350)

st.plotly_chart(fig_power, use_container_width=True)

# ---------------- AUSSCHÜSSE ----------------

st.subheader("📊 Ausschüsse")

fig = go.Figure()

fig.add_bar(name="Männer", y=df["Name"], x=df["Männer"], orientation="h")
fig.add_bar(name="Frauen", y=df["Name"], x=df["Frauen"], orientation="h")

if df["Unbekannt"].sum() > 0:
    fig.add_bar(name="Unbekannt", y=df["Name"], x=df["Unbekannt"], orientation="h")

fig.update_layout(
    barmode="stack",
    height=500,
    margin=dict(l=0, r=0)
)

st.plotly_chart(fig, use_container_width=True)

st.metric("Ausschüsse", len(df))

st.dataframe(
    df[["Name", "Gesamt", "Frauenanteil %"]],
    use_container_width=True,
    hide_index=True
)

# ---------------- DETAIL ----------------

st.subheader("🔍 Ausschuss-Analyse")

selected = st.selectbox("Ausschuss wählen", df["Name"])

org = next(o for o in organizations if o["name"] == selected)

dist = get_committee_distribution(org["id"])

df_dist = pd.DataFrame([
    {"Fraktion": k, "Sitze": v}
    for k, v in dist.items()
]).sort_values("Sitze", ascending=False)

total = df_dist["Sitze"].sum()
df_dist["Anteil %"] = (df_dist["Sitze"] / total * 100).round(1)
df_dist["Mehrheit"] = df_dist["Anteil %"] > 50

fig2 = go.Figure()
fig2.add_bar(
    x=df_dist["Fraktion"],
    y=df_dist["Sitze"],
    text=df_dist["Anteil %"],
    textposition="outside"
)

fig2.update_layout(height=350)

st.plotly_chart(fig2, use_container_width=True)

st.dataframe(df_dist, use_container_width=True, hide_index=True)

# ---------------- FOOTER ----------------

st.markdown("---")
st.markdown("Datenquelle: OParl Grevenbroich")
