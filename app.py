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
                "StartDate": None,
                "LegislativeTerm": None
            })
        else:
            for m in memberships:
                people_list.append({
                    "Name": person.get("name", "Unbekannt"),
                    "Gender": person.get("gender", "Unbekannt"),
                    "Role": m.get("role", "Unbekannt"),
                    "Organization": m.get("organization", "Unbekannt"),
                    "StartDate": m.get("startDate"),
                    "LegislativeTerm": None  # später ersetzen durch Organisation/Ausschuss
                })
    return pd.DataFrame(people_list)

@st.cache_data
def fetch_organizations():
    url = f"{BASE_URL}/organizations"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json().get("data", [])
    orgs = {}
    for o in data:
        orgs[o.get("id", "Unbekannt")] = o.get("name", "Unbekannt")
    return orgs

@st.cache_data
def fetch_terms():
    url = f"{BASE_URL}/legislativeterms"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json().get("data", [])
    terms = {}
    for t in data:
        terms[t.get("id", "Unbekannt")] = t.get("name", "Unbekannt")
    return terms

def main():
    st.title("Stadt Grevenbroich: Ausschüsse & Mitgliederanalyse")

    df_people = fetch_people()
    orgs = fetch_organizations()
    terms = fetch_terms()

    # Ausschussname ersetzen
    df_people["OrganizationName"] = df_people["Organization"].map(orgs).fillna("Unbekannt")
    df_people["LegislativeTermName"] = df_people["LegislativeTerm"].map(terms).fillna("Unbekannt")

    st.sidebar.header("Filter")
    term_filter = st.sidebar.multiselect(
        "Legislaturperiode",
        options=df_people["LegislativeTermName"].unique(),
        default=df_people["LegislativeTermName"].unique()
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

    df_filtered = df_people[
        df_people["LegislativeTermName"].isin(term_filter) &
        df_people["Role"].isin(role_filter) &
        df_people["Gender"].isin(gender_filter)
    ]

    st.subheader("Rohdaten der Mitglieder")
    st.dataframe(df_filtered)

    st.subheader("Geschlechterverteilung pro Ausschuss")
    if not df_filtered.empty:
        gender_count = df_filtered.groupby(["OrganizationName", "Gender"]).size().reset_index(name='Count')
        chart = alt.Chart(gender_count).mark_bar().encode(
            x=alt.X("OrganizationName:N", title="Ausschuss / Organisation"),
            y=alt.Y("Count:Q", title="Anzahl"),
            color=alt.Color("Gender:N", scale=alt.Scale(scheme="category10")),
            tooltip=["OrganizationName", "Gender", "Count"]
        ).properties(width=800, height=400)
        st.altair_chart(chart)
    else:
        st.info("Keine Daten für die gewählten Filter.")

if __name__ == "__main__":
    main()
