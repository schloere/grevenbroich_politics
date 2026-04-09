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
    orgs = {}
    for o in data:
        orgs[o.get("id", "Unbekannt")] = o.get("name", "Unbekannt")
    return orgs

def main():
    st.title("Stadt Grevenbroich: Ausschüsse & Mitgliederanalyse")

    df_people = fetch_people()
    orgs = fetch_organizations()

    # Organisation-ID → Name
    df_people["OrganizationName"] = df_people["Organization"].map(orgs).fillna("Unbekannt")

    st.sidebar.header("Filter")
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
    org_filter = st.sidebar.multiselect(
        "Ausschuss / Organisation",
        options=df_people["OrganizationName"].unique(),
        default=df_people["OrganizationName"].unique()
    )

    # Filter anwenden
    df_filtered = df_people[
        df_people["Role"].isin(role_filter) &
        df_people["Gender"].isin(gender_filter) &
        df_people["OrganizationName"].isin(org_filter)
    ]

    st.subheader("Rohdaten der Mitglieder")
    st.dataframe(df_filtered)

    st.subheader("Geschlechterverteilung nach Ausschuss und Rolle")
    if not df_filtered.empty:
        gender_count = df_filtered.groupby(["OrganizationName", "Role", "Gender"]) \
            .size().reset_index(name='Count')

        chart = alt.Chart(gender_count).mark_bar().encode(
            x=alt.X("OrganizationName:N", title="Ausschuss"),
            y=alt.Y("Count:Q", title="Anzahl"),
            color=alt.Color("Gender:N", scale=alt.Scale(scheme="category10")),
            column=alt.Column("Role:N", title="Rolle"),
            tooltip=["OrganizationName", "Role", "Gender", "Count"]
        ).properties(width=150, height=400)

        st.altair_chart(chart)
    else:
        st.info("Keine Daten für die gewählten Filter.")

if __name__ == "__main__":
    main()
