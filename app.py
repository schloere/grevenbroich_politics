import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime

BASE_URL = "https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013"

@st.cache_data
def fetch_people():
    resp = requests.get(f"{BASE_URL}/people")
    resp.raise_for_status()
    return resp.json().get("data", [])

@st.cache_data
def fetch_organizations():
    resp = requests.get(f"{BASE_URL}/organizations")
    resp.raise_for_status()
    return resp.json().get("data", [])

@st.cache_data
def fetch_memberships():
    resp = requests.get(f"{BASE_URL}/memberships")
    resp.raise_for_status()
    return resp.json().get("data", [])

@st.cache_data
def fetch_legislative_terms():
    resp = requests.get(f"{BASE_URL}/legislativeterms")
    resp.raise_for_status()
    return resp.json().get("data", [])

def main():
    st.title("Grevenbroich – Mitgliederanalyse (neueste Wahlperiode)")

    people = fetch_people()
    orgs = fetch_organizations()
    memberships = fetch_memberships()
    terms = fetch_legislative_terms()

    # Legislaturperioden: sortiert nach Startdatum
    terms_sorted = sorted(
        [t for t in terms if "startDate" in t],
        key=lambda x: x["startDate"],
        reverse=True
    )
    if not terms_sorted:
        st.error("Keine Legislaturperioden gefunden.")
        return

    # Neuste Wahlperiode nehmen
    latest_term = terms_sorted[0]
    term_name = latest_term["name"]
    term_start = datetime.fromisoformat(latest_term["startDate"])
    term_end = datetime.fromisoformat(latest_term.get("endDate", datetime.now().isoformat()))

    st.sidebar.markdown(f"**Analyse für:** {term_name} ({term_start.date()} – {term_end.date()})")

    # Mapping IDs -> Namen/Gender
    person_map = {p["id"]:(p["name"], p.get("gender","Unbekannt")) for p in people}
    org_map = {o["id"]: o.get("name","Unbekannt") for o in orgs}

    # Memberships für die aktuelle Wahlperiode filtern
    rows = []
    for m in memberships:
        sd = m.get("startDate")
        if not sd:
            continue
        try:
            start_date = datetime.fromisoformat(sd[:10])
        except:
            continue
        if term_start <= start_date <= term_end:
            pid = m.get("person")
            rows.append({
                "Person": person_map.get(pid, ("Unbekannt","Unbekannt"))[0],
                "Gender": person_map.get(pid, ("","Unbekannt"))[1],
                "Role": m.get("role","Unbekannt"),
                "Organization": org_map.get(m.get("organization",""),"Unbekannt")
            })

    df = pd.DataFrame(rows)
    if df.empty:
        st.warning(f"Keine Memberships für {term_name} gefunden.")
        return

    # Sidebar Filter
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
