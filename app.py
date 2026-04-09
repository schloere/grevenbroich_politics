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
                "Name": person.get("name"),
                "Gender": person.get("gender") or "Unbekannt",
                "Role": "Keine Mitgliedschaft",
                "Organization": "Keine Organisation",
                "StartDate": None,
                "LegislativeTerm": None
            })
        else:
            for m in memberships:
                # Extrahiere Legislaturperiode aus der Membership-URL
                term_id = m.get("organization", "").split("/")[-1]
                people_list.append({
                    "Name": person.get("name"),
                    "Gender": person.get("gender") or "Unbekannt",
                    "Role": m.get("role") or "Unbekannt",
                    "Organization": m.get("organization") or "Unbekannt",
                    "StartDate": m.get("startDate"),
                    "LegislativeTerm": term_id
                })
    return pd.DataFrame(people_list)

@st.cache_data
def fetch_terms():
    url = f"{BASE_URL}/legislativeterms"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    terms = {}
    for t in data:
        terms[t["id"].split("/")[-1]] = t["name"]
    return terms

def main():
    st.title("Stadt Grevenbroich: Ausschüsse & Mitgliederanalyse")

    df_people = fetch_people()
    terms = fetch_terms()

    # Legislaturperiode-Namen hinzufügen
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

    # Filter anwenden
    df_filtered = df_people[
        df_people["LegislativeTermName"].isin(term_filter) &
        df_people["Role"].isin(role_filter) &
        df_people["Gender"].isin(gender_filter)
    ]

    st.subheader("Rohdaten der Mitglieder")
    st.dataframe(df_filtered)

    st.subheader("Geschlechterverteilung pro Rolle")
    if not df_filtered.empty:
        gender_count = df_filtered.groupby(["Role", "Gender"]).size().reset_index(name='Count')
        chart = alt.Chart(gender_count).mark_bar().encode(
            x=alt.X("Role:N", title="Rolle"),
            y=alt.Y("Count:Q", title="Anzahl"),
            color=alt.Color("Gender:N", scale=alt.Scale(scheme="category10")),
            tooltip=["Role", "Gender", "Count"]
        ).properties(width=700, height=400)
        st.altair_chart(chart)
    else:
        st.info("Keine Daten für die gewählten Filter.")

if __name__ == "__main__":
    main()
