import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime
import time

BASE_URL = "https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013"

# -----------------------------
# ID NORMALISIERUNG (FIX für "Unbekannt")
# -----------------------------
def normalize_id(x):
    if not x:
        return None
    return x.strip().lower().replace("http://", "https://")

# -----------------------------
# ROBUSTES PAGING
# -----------------------------
def fetch_all(url, limit_pages=15):
    all_items = []
    page_count = 0

    progress = st.progress(0)

    while url and page_count < limit_pages:
        for attempt in range(3):  # retry
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:
                if attempt == 2:
                    st.error(f"Fehler beim Laden: {e}")
                    return all_items
                time.sleep(2)

        items = data.get("data", [])
        all_items.extend(items)

        url = data.get("links", {}).get("next")
        page_count += 1

        progress.progress(page_count / limit_pages)

    progress.empty()
    return all_items

# -----------------------------
# CACHED FETCHES
# -----------------------------
@st.cache_data
def fetch_people():
    return fetch_all(f"{BASE_URL}/people")

@st.cache_data
def fetch_orgs():
    return fetch_all(f"{BASE_URL}/organizations")

@st.cache_data
def fetch_memberships():
    return fetch_all(f"{BASE_URL}/memberships")

@st.cache_data
def fetch_terms():
    resp = requests.get(f"{BASE_URL}/legislativeterms", timeout=20)
    resp.raise_for_status()
    return resp.json().get("data", [])

# -----------------------------
# MAIN
# -----------------------------
def main():
    st.title("Grevenbroich – Mitgliederanalyse")

    people = fetch_people()
    orgs = fetch_orgs()
    memberships = fetch_memberships()
    terms = fetch_terms()

    st.write(f"📊 Geladene Datensätze: {len(memberships)} Memberships")

    # -----------------------------
    # WAHLPERIODE (neueste)
    # -----------------------------
    terms_sorted = sorted(
        [t for t in terms if "startDate" in t],
        key=lambda x: x["startDate"],
        reverse=True
    )

    latest_term = terms_sorted[0]
    term_start = datetime.fromisoformat(latest_term["startDate"])
    term_end = datetime.fromisoformat(
        latest_term.get("endDate", datetime.now().isoformat())
    )

    # -----------------------------
    # MAPPINGS (mit NORMALISIERUNG)
    # -----------------------------
    person_map = {
        normalize_id(p["id"]): (
            p.get("name", "Unbekannt"),
            p.get("gender", "Unbekannt")
        )
        for p in people
    }

    org_map = {
        normalize_id(o["id"]): o.get("name", "Unbekannt")
        for o in orgs
    }

    # -----------------------------
    # DATEN AUFBAUEN
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
            pid = normalize_id(m.get("person"))
            oid = normalize_id(m.get("organization"))

            person = person_map.get(pid, ("Unbekannt", "Unbekannt"))

            rows.append({
                "Person": person[0],
                "Gender": person[1],
                "Role": m.get("role", "Unbekannt"),
                "Organization": org_map.get(oid, "Unbekannt")
            })

    df = pd.DataFrame(rows)

    if df.empty:
        st.warning("Keine Daten gefunden.")
        return

    # -----------------------------
    # FILTER
    # -----------------------------
    st.sidebar.header("Filter")

    org_filter = st.sidebar.multiselect(
        "Ausschüsse",
        sorted(df["Organization"].unique()),
        default=sorted(df["Organization"].unique())
    )

    role_filter = st.sidebar.multiselect(
        "Rollen",
        sorted(df["Role"].unique()),
        default=sorted(df["Role"].unique())
    )

    gender_filter = st.sidebar.multiselect(
        "Geschlecht",
        sorted(df["Gender"].unique()),
        default=sorted(df["Gender"].unique())
    )

    df_filtered = df[
        df["Organization"].isin(org_filter) &
        df["Role"].isin(role_filter) &
        df["Gender"].isin(gender_filter)
    ]

    st.dataframe(df_filtered)

    # -----------------------------
    # CHART: AUSSCHÜSSE
    # -----------------------------
    df_org = df_filtered.groupby(
        ["Organization", "Gender"]
    ).size().reset_index(name="Count")

    st.altair_chart(
        alt.Chart(df_org).mark_bar().encode(
            x="Organization:N",
            y="Count:Q",
            color="Gender:N"
        ),
        use_container_width=True
    )

    # -----------------------------
    # CHART: ROLLEN
    # -----------------------------
    df_role = df_filtered.groupby(
        ["Role", "Gender"]
    ).size().reset_index(name="Count")

    st.altair_chart(
        alt.Chart(df_role).mark_bar().encode(
            x="Role:N",
            y="Count:Q",
            color="Gender:N"
        ),
        use_container_width=True
    )

    # -----------------------------
    # HEATMAP
    # -----------------------------
    df_heat = df_filtered.groupby(
        ["Organization", "Role", "Gender"]
    ).size().reset_index(name="Count")

    charts = []
    for g in df_heat["Gender"].unique():
        dfg = df_heat[df_heat["Gender"] == g]

        charts.append(
            alt.Chart(dfg).mark_rect().encode(
                x="Organization:N",
                y="Role:N",
                color="Count:Q"
            ).properties(title=g)
        )

    st.altair_chart(alt.hconcat(*charts), use_container_width=True)


if __name__ == "__main__":
    main()
