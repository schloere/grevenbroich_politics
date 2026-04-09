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
    data = response.json()["data"]
    people_list = []
    for person in data:
        memberships = person.get("membership", [])
        for m in memberships:
            people_list.append({
                "Name": person.get("name"),
                "Gender": person.get("gender"),
                "Role": m.get("role"),
                "Organization": m.get("organization"),
                "VotingRight": m.get("votingRight"),
                "StartDate": m.get("startDate")
            })
    return pd.DataFrame(people_list)

def main():
    st.title("Stadt Grevenbroich: Ausschüsse & Personen")
    st.markdown(
        """
        Analyse der Mitglieder nach Geschlecht in den Ausschüssen.
        Datenquelle: [OParl Grevenbroich](https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013)
        """
    )

    df_people = fetch_people()

    st.subheader("Rohdaten der Mitglieder")
    st.dataframe(df_people)

    st.subheader("Geschlechterverteilung nach Rolle")
    gender_count = df_people.groupby(["Role", "Gender"]).size().reset_index(name='Count')

    chart = alt.Chart(gender_count).mark_bar().encode(
        x=alt.X("Role:N", title="Rolle"),
        y=alt.Y("Count:Q", title="Anzahl"),
        color=alt.Color("Gender:N", scale=alt.Scale(scheme="category10")),
        tooltip=["Role", "Gender", "Count"]
    ).properties(width=700, height=400)

    st.altair_chart(chart)

if __name__ == "__main__":
    main()
