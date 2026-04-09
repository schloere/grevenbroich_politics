import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime

# Zeitraum der 11. Wahlperiode definieren
TERM_START = datetime(2025, 11, 1)
TERM_END = datetime(2030, 10, 31)

BASE_URL = "https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013"

@st.cache_data
def fetch_people():
    url = f"{BASE_URL}/people"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json().get("data", [])

@st.cache_data
def fetch_organizations():
    url = f"{BASE_URL}/organizations"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json().get("data", [])

@st.cache_data
def fetch_memberships():
    url = f"{BASE_URL}/memberships"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json().get("data", [])

def in_term(date_str):
    try:
        d = datetime.fromisoformat(date_str[:-1])
        return TERM_START <= d <= TERM_END
    except:
        return False

def main():
    st.title("Grevenbroich – 11. Wahlperiode Mitgliederanalyse (zeitbasiert)")

    people = fetch_people()
    orgs = fetch_organizations()
    memberships = fetch_memberships()

    # Mapping Person & Organisation
    person_map = {p["id"]:(p["name"], p.get("gender","Unbekannt")) for p in people}
    org_map = {o["id"]: o["name"] for o in orgs}

    rows = []
    for m in memberships:
        sd = m.get("startDate")
        if sd and in_term(sd):
            pid = m.get("person")
            rows.append({
                "Person": person_map.get(pid,("Unbekannt","Unbekannt"))[0],
                "Gender": person_map.get(pid,("","Unbekannt"))[1],
                "Role": m.get("role","Unbekannt"),
                "Organization": org_map.get(m.get("organization",""),"Unbekannt")
            })

    df = pd.DataFrame(rows)
    if df.empty:
        st.warning("Für die 11. Wahlperiode (zeitbasiert) wurden keine Memberships gefunden.")
        return

    st.sidebar.header("Filter")
    org_filter = st.sidebar.multiselect("Ausschuss / Organisation",
                                        options=df["Organization"].unique(),
                                        default=df["Organization"].unique())
    role_filter = st.sidebar.multiselect("Rolle",
                                         options=df["Role"].unique(),
                                         default=df["Role"].unique())
    gender_filter = st.sidebar.multiselect("Geschlecht",
                                           options=df["Gender"].unique(),
                                           default=df["Gender"].unique())

    show_org_chart = st.sidebar.checkbox("Ausschüsse", value=True)
    show_role_chart = st.sidebar.checkbox("Rollen", value=True)
    show_heatmap = st.sidebar.checkbox("Heatmap", value=True)

    df_filtered = df[
        df["Organization"].isin(org_filter) &
        df["Role"].isin(role_filter) &
        df["Gender"].isin(gender_filter)
    ]

    st.subheader("Mitglieder Rohdaten")
    st.dataframe(df_filtered)

    if show_org_chart:
        st.subheader("Geschlechterverteilung pro Ausschuss")
        df_org = df_filtered.groupby(["Organization","Gender"]).size().reset_index(name="Count")
        c1 = alt.Chart(df_org).mark_bar().encode(
            x="Organization:N", y="Count:Q",
            color="Gender:N", tooltip=["Organization","Gender","Count"]
        ).properties(width=700,height=350)
        st.altair_chart(c1)

    if show_role_chart:
        st.subheader("Geschlechterverteilung nach Rolle")
        df_role = df_filtered.groupby(["Role","Gender"]).size().reset_index(name="Count")
        c2 = alt.Chart(df_role).mark_bar().encode(
            x="Role:N", y="Count:Q",
            color="Gender:N", tooltip=["Role","Gender","Count"]
        ).properties(width=700,height=350)
        st.altair_chart(c2)

    if show_heatmap:
        st.subheader("Heatmap: Ausschuss × Rolle × Geschlecht")
        df_heat = df_filtered.groupby(["Organization","Role","Gender"]).size().reset_index(name="Count")
        charts = []
        for g in df_heat["Gender"].unique():
            dfg = df_heat[df_heat["Gender"]==g]
            c = alt.Chart(dfg).mark_rect().encode(
                x="Organization:N", y="Role:N",
                color=alt.Color("Count:Q", scale=alt.Scale(scheme="reds")),
                tooltip=["Organization","Role","Count"]
            ).properties(title=f"{g}",width=150,height=350)
            charts.append(c)
        st.altair_chart(alt.hconcat(*charts))

if __name__ == "__main__":
    main()
