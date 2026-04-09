import streamlit as st
import requests
import pandas as pd
import altair as alt

BASE_URL = "https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013"

@st.cache_data
def fetch_people():
    url = f"{BASE_URL}/people"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json().get("data", [])
    people_list = []

    for person in data:
        memberships = person.get("membership", [])
        if not memberships:
            people_list.append({
                "Name": person.get("name", "Unbekannt"),
                "Gender": person.get("gender", "Unbekannt"),
                "Role": "Keine Mitgliedschaft",
                "Organization": "Keine Organisation",
                "StartDate": None
            })
        else:
            for m in memberships:
                people_list.append({
                    "Name": person.get("name", "Unbekannt"),
                    "Gender": person.get("gender", "Unbekannt"),
                    "Role": m.get("role", "Unbekannt"),
                    "Organization": m.get("organization", "Unbekannt"),
                    "StartDate": m.get("startDate")
                })
    return pd.DataFrame(people_list)

@st.cache_data
def fetch_organizations():
    url = f"{BASE_URL}/organizations"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json().get("data", [])
    orgs = {o.get("id", "Unbekannt"): o.get("name", "Unbekannt") for o in data}
    return orgs

def main():
    st.title("Stadt Grevenbroich: Mitgliederanalyse nach Ausschuss und Rolle")

    df_people = fetch_people()
    orgs = fetch_organizations()

    # Organisation-ID → Name
    df_people["OrganizationName"] = df_people["Organization"].map(orgs).fillna("Unbekannt")

    # Sidebar-Filter
    st.sidebar.header("Filter")
    org_filter = st.sidebar.multiselect(
        "Ausschuss / Organisation",
        options=df_people["OrganizationName"].unique(),
        default=df_people["OrganizationName"].unique()
    )
    role_filter = st.sidebar.multiselect(
        "Rolle",
        options=df_people["Role"].unique(),
        default=df_people["Role"].unique()
    )
    gender_filter = st.sidebar.multiselect(
        "Geschlecht",
        options=df_people["Gender"].unique(),
        default=df_people["Gender"].unique()
    )

    # Filter anwenden
    df_filtered = df_people[
        df_people["OrganizationName"].isin(org_filter) &
        df_people["Role"].isin(role_filter) &
        df_people["Gender"].isin(gender_filter)
    ]

    st.subheader("Rohdaten der Mitglieder")
    st.dataframe(df_filtered)

    # Grafik 1: Ausschüsse
    st.subheader("Geschlechterverteilung pro Ausschuss")
    if not df_filtered.empty:
        df_org = df_filtered.groupby(["OrganizationName", "Gender"]).size().reset_index(name='Count')
        chart_org = alt.Chart(df_org).mark_bar().encode(
            x=alt.X("OrganizationName:N", title="Ausschuss"),
            y=alt.Y("Count:Q", title="Anzahl"),
            color=alt.Color("Gender:N", scale=alt.Scale(scheme="category10")),
            tooltip=["OrganizationName", "Gender", "Count"]
        ).properties(width=700, height=400)
        st.altair_chart(chart_org)
    else:
        st.info("Keine Daten für die gewählten Filter.")

    # Grafik 2: Rollen
    st.subheader("Geschlechterverteilung nach Rolle")
    if not df_filtered.empty:
        df_role = df_filtered.groupby(["Role", "Gender"]).size().reset_index(name='Count')
        chart_role = alt.Chart(df_role).mark_bar().encode(
            x=alt.X("Role:N", title="Rolle"),
            y=alt.Y("Count:Q", title="Anzahl"),
            color=alt.Color("Gender:N", scale=alt.Scale(scheme="category10")),
            tooltip=["Role", "Gender", "Count"]
        ).properties(width=700, height=400)
        st.altair_chart(chart_role)

    # Grafik 3: Heatmap Ausschuss x Rolle
    st.subheader("Heatmap: Ausschuss x Rolle x Geschlecht")
    if not df_filtered.empty:
        df_heat = df_filtered.groupby(["OrganizationName", "Role", "Gender"]).size().reset_index(name='Count')
        chart_heat = alt.Chart(df_heat).mark_rect().encode(
            x=alt.X("OrganizationName:N", title="Ausschuss"),
            y=alt.Y("Role:N", title="Rolle"),
            color=alt.Color("Count:Q", scale=alt.Scale(scheme="reds")),
            tooltip=["OrganizationName", "Role", "Gender", "Count"]
        ).facet(
            column="Gender:N"
        ).properties(width=150, height=400)
        st.altair_chart(chart_heat)

if __name__ == "__main__":
    main()
