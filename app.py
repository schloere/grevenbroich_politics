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
        if not memberships:  # Personen ohne Mitgliedschaft
            people_list.append({
                "Name": person.get("name"),
                "Gender": person.get("gender") or "Unbekannt",
                "Role": "Keine Mitgliedschaft",
                "Organization": None,
                "VotingRight": None,
                "StartDate": None
            })
        else:
            for m in memberships:
                people_list.append({
                    "Name": person.get("name"),
                    "Gender": person.get("gender") or "Unbekannt",
                    "Role": m.get("role") or "Unbekannt",
                    "Organization": m.get("organization"),
                    "VotingRight": m.get("votingRight"),
                    "StartDate": m.get("startDate")
                })
    return pd.DataFrame(people_list)

def main():
    st.title("Stadt Grevenbroich: Ausschüsse & Personen")
    df_people = fetch_people()

    st.subheader("Rohdaten der Mitglieder")
    st.dataframe(df_people)

    st.subheader("Geschlechterverteilung nach Rolle")
    if "Role" in df_people.columns and "Gender" in df_people.columns:
        gender_count = df_people.groupby(["Role", "Gender"]).size().reset_index(name='Count')
        chart = alt.Chart(gender_count).mark_bar().encode(
            x=alt.X("Role:N", title="Rolle"),
            y=alt.Y("Count:Q", title="Anzahl"),
            color=alt.Color("Gender:N", scale=alt.Scale(scheme="category10")),
            tooltip=["Role", "Gender", "Count"]
        ).properties(width=700, height=400)
        st.altair_chart(chart)
    else:
        st.warning("Die benötigten Spalten 'Role' oder 'Gender' fehlen.")

if __name__ == "__main__":
    main()
