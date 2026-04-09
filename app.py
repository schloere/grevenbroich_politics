import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime

BASE_URL = "https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013"

# -----------------------------
# PAGING (robust & begrenzt)
# -----------------------------
def fetch_all(url, limit_pages=20):
    all_items = []
    page_count = 0

    progress = st.progress(0)

    while url and page_count < limit_pages:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            st.error(f"Fehler beim Laden: {e}")
            break

        items = data.get("data", [])
        all_items.extend(items)

        url = data.get("links", {}).get("next")
        page_count += 1

        progress.progress(min(page_count / limit_pages, 1.0))

    progress.empty()
    return all_items

# -----------------------------
# CACHED FETCHES
# -----------------------------
@st.cache_data
def fetch_people():
    return fetch_all(f"{BASE_URL}/people")

@st.cache_data
def fetch_organizations():
    return fetch_all(f"{BASE_URL}/organizations")

@st.cache_data
def fetch_memberships():
    return fetch_all(f"{BASE_URL}/memberships")

@st.cache_data
def fetch_terms():
    resp = requests.get(f"{BASE_URL}/legislativeterms")
    resp.raise_for_status()
    return resp.json().get("data", [])

# -----------------------------
# MAIN
# -----------------------------
def main():
    st.title("Stadt Grevenbroich: Ausschüsse & Mitgliederanalyse")

    people = fetch_people()
    orgs = fetch_organizations()
    memberships = fetch_memberships()
    terms = fetch_terms()

    if not memberships:
        st.warning("Keine Membership-Daten geladen.")
        return

    # -----------------------------
    # Wahlperiode bestimmen (neueste)
    # -----------------------------
    terms_sorted = sorted(
        [t for t in terms if "startDate" in t],
        key=lambda x: x["startDate"],
        reverse=True
    )

    latest_term = terms_sorted[0]
    term_name = latest_term["name"]
    term_start = datetime.fromisoformat(latest_term["startDate"])
    term_end = datetime.fromisoformat(
        latest_term.get("endDate", datetime.now().isoformat())
    )

    st.sidebar.markdown(f"**Analyse für:** {term_name}")

    # -----------------------------
    # Mapping
    # -----------------------------
    person_map = {
        p["id"]: (p["name"], p.get("gender", "Unbekannt"))
        for p in people
    }

    org_map = {
        o["id"]: o.get("name", "Unbekannt")
        for o in orgs
    }

    # -----------------------------
    # Daten bauen
    # -----------------------------
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
                "Person": person_map.get(pid, ("Unbekannt", "Unbekannt"))[0],
                "Gender": person_map.get(pid, ("", "Unbekannt"))[1],
                "Role": m.get("role", "Unbekannt"),
                "Organization": org_map.get(
                    m.get("organization", ""), "Unbekannt"
                )
            })

    df = pd.DataFrame(rows)

    if df.empty:
        st.warning("Keine Daten für diese Wahlperiode gefunden.")
        return

    # -----------------------------
    # SIDEBAR FILTER
    # -----------------------------
    st.sidebar.header("Filter")

    org_filter = st.sidebar.multiselect(
        "Ausschüsse",
        options=sorted(df["Organization"].unique()),
        default=sorted(df["Organization"].unique())
    )

    role_filter = st.sidebar.multiselect(
        "Rollen",
        options=sorted(df["Role"].unique()),
        default=sorted(df["Role"].unique())
    )

    gender_filter = st.sidebar.multiselect(
        "Geschlecht",
        options=sorted(df["Gender"].unique()),
        default=sorted(df["Gender"].unique())
    )

    show_org_chart = st.sidebar.checkbox("Ausschüsse anzeigen", True)
    show_role_chart = st.sidebar.checkbox("Rollen anzeigen", True)
    show_heatmap = st.sidebar.checkbox("Heatmap anzeigen", True)

    # -----------------------------
    # FILTER ANWENDEN
    # -----------------------------
    df_filtered = df[
        df["Organization"].isin(org_filter) &
        df["Role"].isin(role_filter) &
        df["Gender"].isin(gender_filter)
    ]

    st.subheader("Rohdaten")
    st.dataframe(df_filtered)

    # -----------------------------
    # CHART 1: AUSSCHÜSSE
    # -----------------------------
    if show_org_chart:
        st.subheader("Geschlechterverteilung pro Ausschuss")

        df_org = df_filtered.groupby(
            ["Organization", "Gender"]
        ).size().reset_index(name="Count")

        chart1 = alt.Chart(df_org).mark_bar().encode(
            x="Organization:N",
            y="Count:Q",
            color="Gender:N",
            tooltip=["Organization", "Gender", "Count"]
        ).properties(width=700, height=350)

        st.altair_chart(chart1, use_container_width=True)

    # -----------------------------
    # CHART 2: ROLLEN
    # -----------------------------
    if show_role_chart:
        st.subheader("Geschlechterverteilung nach Rolle")

        df_role = df_filtered.groupby(
            ["Role", "Gender"]
        ).size().reset_index(name="Count")

        chart2 = alt.Chart(df_role).mark_bar().encode(
            x="Role:N",
            y="Count:Q",
            color="Gender:N",
            tooltip=["Role", "Gender", "Count"]
        ).properties(width=700, height=350)

        st.altair_chart(chart2, use_container_width=True)

    # -----------------------------
    # HEATMAP
    # -----------------------------
    if show_heatmap:
        st.subheader("Heatmap: Ausschuss × Rolle × Geschlecht")

        df_heat = df_filtered.groupby(
            ["Organization", "Role", "Gender"]
        ).size().reset_index(name="Count")

        charts = []

        for g in df_heat["Gender"].unique():
            dfg = df_heat[df_heat["Gender"] == g]

            c = alt.Chart(dfg).mark_rect().encode(
                x="Organization:N",
                y="Role:N",
                color=alt.Color("Count:Q", scale=alt.Scale(scheme="reds")),
                tooltip=["Organization", "Role", "Count"]
            ).properties(
                title=g,
                width=200,
                height=350
            )

            charts.append(c)

        st.altair_chart(alt.hconcat(*charts), use_container_width=True)


if __name__ == "__main__":
    main()
