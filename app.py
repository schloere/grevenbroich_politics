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
    data = resp.json().get("data", [])
    return {t["id"]: t["name"] for t in data}

@st.cache_data
def fetch_organizations():
    url = f"{BASE_URL}/organizations"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    orgs = {}
    for o in data:
        orgs[o["id"]] = {
            "name": o.get("name", "Unbekannt"),
            "legislativeTerm": o.get("legislativeTerm", "")
        }
    return orgs

@st.cache_data
def fetch_people():
    url = f"{BASE_URL}/people"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    people_list = []
    for p in data:
        memberships = p.get("membership", [])
        for m in memberships:
            people_list.append({
                "Name": p.get("name", "Unbekannt"),
                "Gender": p.get("gender", "Unbekannt"),
                "Role": m.get("role", "Unbekannt"),
                "OrganizationID": m.get("organization", ""),
                "StartDate": m.get("startDate")
            })
    return pd.DataFrame(people_list)

def main():
    st.title("Stadt Grevenbroich – Mitgliederanalyse 11. Wahlperiode 2025-2030")

    # Legislaturperioden + Organisationen laden
    terms = fetch_legislative_terms()
    orgs = fetch_organizations()
    
    df_people = fetch_people()
    
    # OrganizationID → Name + LegislaturTermID
    df_people["OrganizationName"] = df_people["OrganizationID"].map(lambda x: orgs.get(x, {}).get("name", "Unbekannt"))
    df_people["LegislativeTermID"] = df_people["OrganizationID"].map(lambda x: orgs.get(x, {}).get("legislativeTerm", ""))
    df_people["LegislativeTermName"] = df_people["LegislativeTermID"].map(lambda x: terms.get(x, "Unbekannt"))

    # Nur 11. Wahlperiode
    df_people = df_people[df_people["LegislativeTermName"] == TARGET_TERM_NAME]

    if df_people.empty:
        st.warning("Keine Daten für die 11. Wahlperiode gefunden.")
        return

    # Sidebar Filter
    st.sidebar.header("Filter")
    org_filter = st.sidebar.multiselect("Ausschuss / Organisation",
                                        options=df_people["OrganizationName"].unique(),
                                        default=df_people["OrganizationName"].unique())
    role_filter = st.sidebar.multiselect("Rolle",
                                         options=df_people["Role"].unique(),
                                         default=df_people["Role"].unique())
    gender_filter = st.sidebar.multiselect("Geschlecht",
                                           options=df_people["Gender"].unique(),
                                           default=df_people["Gender"].unique())

    st.sidebar.header("Diagramme anzeigen")
    show_org_chart = st.sidebar.checkbox("Ausschüsse", value=True)
    show_role_chart = st.sidebar.checkbox("Rollen", value=True)
    show_heatmap = st.sidebar.checkbox("Heatmap", value=True)

    df_filtered = df_people[
        df_people["OrganizationName"].isin(org_filter) &
        df_people["Role"].isin(role_filter) &
        df_people["Gender"].isin(gender_filter)
    ]

    st.subheader("Rohdaten der Mitglieder")
    st.dataframe(df_filtered)

    # Ausschüsse
    if show_org_chart:
        st.subheader("Geschlechterverteilung pro Ausschuss")
        df_org = df_filtered.groupby(["OrganizationName", "Gender"]).size().reset_index(name="Count")
        chart_org = alt.Chart(df_org).mark_bar().encode(
            x="OrganizationName:N",
            y="Count:Q",
            color="Gender:N",
            tooltip=["OrganizationName", "Gender", "Count"]
        ).properties(width=700, height=400)
        st.altair_chart(chart_org)

    # Rollen
    if show_role_chart:
        st.subheader("Geschlechterverteilung nach Rolle")
        df_role = df_filtered.groupby(["Role", "Gender"]).size().reset_index(name="Count")
        chart_role = alt.Chart(df_role).mark_bar().encode(
            x="Role:N",
            y="Count:Q",
            color="Gender:N",
            tooltip=["Role", "Gender", "Count"]
        ).properties(width=700, height=400)
        st.altair_chart(chart_role)

    # Heatmap
    if show_heatmap:
        st.subheader("Heatmap: Ausschuss x Rolle x Geschlecht")
        df_heat = df_filtered.groupby(["OrganizationName", "Role", "Gender"]).size().reset_index(name="Count")
        charts = []
        for gender in df_heat["Gender"].unique():
            df_gender = df_heat[df_heat["Gender"] == gender]
            chart = alt.Chart(df_gender).mark_rect().encode(
                x="OrganizationName:N",
                y="Role:N",
                color=alt.Color("Count:Q", scale=alt.Scale(scheme="reds")),
                tooltip=["OrganizationName", "Role", "Count"]
            ).properties(width=150, height=400, title=f"Geschlecht: {gender}")
            charts.append(chart)
        st.altair_chart(alt.hconcat(*charts))

if __name__ == "__main__":
    main()
