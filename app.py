import streamlit as st
import requests
import pandas as pd
import altair as alt

BASE_URL = "https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013"
TARGET_TERM_NAME = "11. Wahlperiode 2025 - 2030"

@st.cache_data
def fetch_legislative_terms():
    url = f"{BASE_URL}/legislativeterms"
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
def fetch_people():
    url = f"{BASE_URL}/people"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json().get("data", [])

@st.cache_data
def fetch_memberships():
    url = f"{BASE_URL}/memberships"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json().get("data", [])

def main():
    st.title("Grevenbroich: Analyse Mitglieder 11. Wahlperiode 2025–2030")

    terms = fetch_legislative_terms()
    orgs = fetch_organizations()
    people = fetch_people()
    memberships = fetch_memberships()

    # Legislaturperioden map (ID -> Name)
    term_map = {t["id"]: t["name"] for t in terms}

    # Organisationen map (ID -> Name)
    org_map = {o["id"]: o["name"] for o in orgs}

    # Personen map (ID -> Name, Gender)
    person_map = {p["id"]: (p["name"], p.get("gender", "Unbekannt")) for p in people}

    # Alle Memberships sauber aufbereiten
    rows = []
    for m in memberships:
        term = term_map.get(m.get("legislativeTerm"), "")
        if term == TARGET_TERM_NAME:
            pid = m.get("person")
            rows.append({
                "Person": person_map.get(pid, ("Unbekannt", "Unbekannt"))[0],
                "Gender": person_map.get(pid, ("", "Unbekannt"))[1],
                "Role": m.get("role", "Unbekannt"),
                "Organization": org_map.get(m.get("organization", ""), "Unbekannt"),
            })

    df = pd.DataFrame(rows)
    if df.empty:
        st.warning("Für die 11. Wahlperiode wurden keine Mitgliedschaften gefunden.")
        return

    # Sidebar: Filter
    st.sidebar.header("Filter")
    org_filter = st.sidebar.multiselect(
        "Ausschuss / Organisation",
        options=df["Organization"].unique(),
        default=df["Organization"].unique()
    )
    role_filter = st.sidebar.multiselect(
        "Rolle",
        options=df["Role"].unique(),
        default=df["Role"].unique()
    )
    gender_filter = st.sidebar.multiselect(
        "Geschlecht",
        options=df["Gender"].unique(),
        default=df["Gender"].unique()
    )

    st.sidebar.header("Diagramme anzeigen")
    show_org_chart = st.sidebar.checkbox("Ausschüsse", value=True)
    show_role_chart = st.sidebar.checkbox("Rollen", value=True)
    show_heatmap = st.sidebar.checkbox("Heatmap", value=True)

    df_filtered = df[
        df["Organization"].isin(org_filter) &
        df["Role"].isin(role_filter) &
        df["Gender"].isin(gender_filter)
    ]

    st.subheader("Rohdaten der Mitglieder")
    st.dataframe(df_filtered)

    # Ausschüsse
    if show_org_chart:
        st.subheader("Geschlechterverteilung pro Ausschuss")
        df_org = df_filtered.groupby(["Organization", "Gender"]).size().reset_index(name="Count")
        chart_org = alt.Chart(df_org).mark_bar().encode(
            x="Organization:N",
            y="Count:Q",
            color="Gender:N",
            tooltip=["Organization","Gender","Count"]
        ).properties(width=700, height=400)
        st.altair_chart(chart_org)

    # Rollen
    if show_role_chart:
        st.subheader("Geschlechterverteilung nach Rolle")
        df_role = df_filtered.groupby(["Role","Gender"]).size().reset_index(name="Count")
        chart_role = alt.Chart(df_role).mark_bar().encode(
            x="Role:N",
            y="Count:Q",
            color="Gender:N",
            tooltip=["Role","Gender","Count"]
        ).properties(width=700, height=400)
        st.altair_chart(chart_role)

    # Heatmap
    if show_heatmap:
        st.subheader("Heatmap: Ausschuss x Rolle x Geschlecht")
        df_heat = df_filtered.groupby(["Organization","Role","Gender"]).size().reset_index(name="Count")
        charts = []
        for gender in df_heat["Gender"].unique():
            df_g = df_heat[df_heat["Gender"]==gender]
            chart = alt.Chart(df_g).mark_rect().encode(
                x="Organization:N",
                y="Role:N",
                color=alt.Color("Count:Q", scale=alt.Scale(scheme="reds")),
                tooltip=["Organization","Role","Count"]
            ).properties(title=f"{gender}", width=150, height=400)
            charts.append(chart)
        st.altair_chart(alt.hconcat(*charts))

if __name__ == "__main__":
    main()
