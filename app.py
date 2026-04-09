import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime
import time

BASE_URL = "https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013"

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def normalize_id(x):
    """Vereinheitlicht OParl-IDs (http vs https, trailing spaces)."""
    if not x:
        return None
    return x.strip().lower().replace("http://", "https://")


def fetch_all(url, label="Daten", limit_pages=30):
    """Lädt alle Seiten einer OParl-Resource mit Retry + Fortschrittsanzeige."""
    all_items = []
    page_count = 0
    bar = st.progress(0, text=f"Lade {label}…")

    while url and page_count < limit_pages:
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:
                if attempt == 2:
                    st.error(f"Fehler beim Laden von {label}: {e}")
                    bar.empty()
                    return all_items
                time.sleep(2)

        all_items.extend(data.get("data", []))
        url = data.get("links", {}).get("next")
        page_count += 1
        bar.progress(min(page_count / limit_pages, 1.0), text=f"Lade {label}… ({len(all_items)} bisher)")

    bar.empty()
    return all_items


# ─────────────────────────────────────────────
# CACHED FETCHES
# ─────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def fetch_people():
    return fetch_all(f"{BASE_URL}/people", "Personen")

@st.cache_data(show_spinner=False)
def fetch_orgs():
    return fetch_all(f"{BASE_URL}/organizations", "Organisationen")

@st.cache_data(show_spinner=False)
def fetch_memberships():
    return fetch_all(f"{BASE_URL}/memberships", "Mitgliedschaften")

@st.cache_data(show_spinner=False)
def fetch_terms():
    resp = requests.get(f"{BASE_URL}/legislativeterms", timeout=20)
    resp.raise_for_status()
    # Grevenbroich gibt die Terms direkt im Body zurück, kein "data"-Key
    raw = resp.json()
    if isinstance(raw, list):
        return raw
    return raw.get("data", raw.get("legislativeTerm", []))


# ─────────────────────────────────────────────
# DATEN AUFBEREITEN
# ─────────────────────────────────────────────

def build_dataframe(memberships, person_map, org_map, term_start, term_end):
    rows = []
    for m in memberships:
        sd = m.get("startDate")
        if not sd:
            continue
        try:
            start_date = datetime.fromisoformat(sd[:10])
        except Exception:
            continue

        if not (term_start <= start_date <= term_end):
            continue

        pid = normalize_id(m.get("person"))
        oid = normalize_id(m.get("organization"))
        name, gender = person_map.get(pid, ("Unbekannt", "Unbekannt"))

        rows.append({
            "Person":       name,
            "Geschlecht":   gender,
            "Rolle":        m.get("role", "Unbekannt"),
            "Ausschuss":    org_map.get(oid, "Unbekannt"),
            "StartDatum":   sd[:10],
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# VISUALISIERUNGEN
# ─────────────────────────────────────────────

def chart_ausschuesse(df):
    df_agg = df.groupby(["Ausschuss", "Geschlecht"]).size().reset_index(name="Anzahl")
    return (
        alt.Chart(df_agg)
        .mark_bar()
        .encode(
            x=alt.X("Ausschuss:N", sort="-y", title="Ausschuss"),
            y=alt.Y("Anzahl:Q"),
            color=alt.Color(
                "Geschlecht:N",
                scale=alt.Scale(
                    domain=["weiblich", "männlich", "divers", "Unbekannt"],
                    range=["#e63946", "#457b9d", "#2a9d8f", "#aaa"],
                ),
            ),
            tooltip=["Ausschuss", "Geschlecht", "Anzahl"],
        )
        .properties(height=380)
    )


def chart_rollen(df):
    df_agg = df.groupby(["Rolle", "Geschlecht"]).size().reset_index(name="Anzahl")
    return (
        alt.Chart(df_agg)
        .mark_bar()
        .encode(
            x=alt.X("Rolle:N", sort="-y"),
            y=alt.Y("Anzahl:Q"),
            color=alt.Color(
                "Geschlecht:N",
                scale=alt.Scale(
                    domain=["weiblich", "männlich", "divers", "Unbekannt"],
                    range=["#e63946", "#457b9d", "#2a9d8f", "#aaa"],
                ),
            ),
            tooltip=["Rolle", "Geschlecht", "Anzahl"],
        )
        .properties(height=320)
    )


def chart_heatmap(df):
    df_agg = (
        df.groupby(["Ausschuss", "Rolle", "Geschlecht"])
        .size()
        .reset_index(name="Anzahl")
    )
    charts = []
    for g in sorted(df_agg["Geschlecht"].unique()):
        dfg = df_agg[df_agg["Geschlecht"] == g]
        c = (
            alt.Chart(dfg)
            .mark_rect()
            .encode(
                x=alt.X("Ausschuss:N", title="Ausschuss"),
                y=alt.Y("Rolle:N", title="Rolle"),
                color=alt.Color("Anzahl:Q", scale=alt.Scale(scheme="reds")),
                tooltip=["Ausschuss", "Rolle", "Anzahl"],
            )
            .properties(title=g, width=200, height=300)
        )
        charts.append(c)
    return alt.hconcat(*charts) if charts else None


def frauenquoten_tabelle(df):
    """Berechnet Frauenquote pro Ausschuss und markiert <30 %."""
    total = df.groupby("Ausschuss").size().rename("Gesamt")
    frauen = (
        df[df["Geschlecht"] == "weiblich"]
        .groupby("Ausschuss")
        .size()
        .rename("Frauen")
    )
    tbl = pd.concat([total, frauen], axis=1).fillna(0)
    tbl["Frauen"] = tbl["Frauen"].astype(int)
    tbl["Quote (%)"] = (tbl["Frauen"] / tbl["Gesamt"] * 100).round(1)
    tbl = tbl.sort_values("Quote (%)")
    tbl["⚠️"] = tbl["Quote (%)"].apply(lambda q: "🔴 <30 %" if q < 30 else "✅")
    return tbl.reset_index()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    st.set_page_config(page_title="Grevenbroich – Mitgliederanalyse", layout="wide")
    st.title("🏛️ Stadt Grevenbroich – Mitgliederanalyse")
    st.caption("Datenquelle: [OParl Grevenbroich](https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013)")

    # ── Daten laden ──
    with st.spinner("Lade Stammdaten…"):
        people      = fetch_people()
        orgs        = fetch_orgs()
        memberships = fetch_memberships()
        terms       = fetch_terms()

    st.sidebar.success(f"✅ {len(memberships)} Mitgliedschaften geladen")

    # ── Wahlperiode wählen ──
    valid_terms = [t for t in terms if t.get("startDate") and t.get("name")]
    valid_terms_sorted = sorted(valid_terms, key=lambda x: x["startDate"], reverse=True)
    term_names = [t["name"] for t in valid_terms_sorted]

    selected_term_name = st.sidebar.selectbox("Wahlperiode", term_names, index=0)
    selected_term = next(t for t in valid_terms_sorted if t["name"] == selected_term_name)

    term_start = datetime.fromisoformat(selected_term["startDate"])
    term_end   = datetime.fromisoformat(
        selected_term.get("endDate", datetime.now().date().isoformat())
    )
    st.sidebar.caption(f"{term_start.date()} – {term_end.date()}")

    # ── Mappings ──
    person_map = {
        normalize_id(p["id"]): (p.get("name", "Unbekannt"), p.get("gender", "Unbekannt"))
        for p in people
    }
    org_map = {
        normalize_id(o["id"]): o.get("name", "Unbekannt")
        for o in orgs
    }

    # ── DataFrame bauen ──
    df = build_dataframe(memberships, person_map, org_map, term_start, term_end)

    if df.empty:
        st.warning(
            f"Keine Mitgliedschaften für **{selected_term_name}** gefunden. "
            "Möglicherweise sind die Daten in der API noch nicht vollständig eingetragen."
        )
        return

    # ── Sidebar Filter ──
    st.sidebar.header("🔍 Filter")

    ausschuss_filter = st.sidebar.multiselect(
        "Ausschuss", sorted(df["Ausschuss"].unique()), default=sorted(df["Ausschuss"].unique())
    )
    rollen_filter = st.sidebar.multiselect(
        "Rolle", sorted(df["Rolle"].unique()), default=sorted(df["Rolle"].unique())
    )
    gender_filter = st.sidebar.multiselect(
        "Geschlecht", sorted(df["Geschlecht"].unique()), default=sorted(df["Geschlecht"].unique())
    )

    st.sidebar.header("📊 Diagramme")
    show_ausschuss = st.sidebar.checkbox("Geschlecht pro Ausschuss", True)
    show_rollen    = st.sidebar.checkbox("Geschlecht pro Rolle", True)
    show_heatmap   = st.sidebar.checkbox("Heatmap", True)
    show_quote     = st.sidebar.checkbox("Frauenquoten-Ranking", True)

    # ── Filter anwenden ──
    df_f = df[
        df["Ausschuss"].isin(ausschuss_filter) &
        df["Rolle"].isin(rollen_filter) &
        df["Geschlecht"].isin(gender_filter)
    ]

    # ── KPIs ──
    col1, col2, col3, col4 = st.columns(4)
    total = len(df_f)
    frauen = (df_f["Geschlecht"] == "weiblich").sum()
    maenner = (df_f["Geschlecht"] == "männlich").sum()
    quote = round(frauen / total * 100, 1) if total > 0 else 0

    col1.metric("Mitglieder gesamt", total)
    col2.metric("Frauen", frauen)
    col3.metric("Männer", maenner)
    col4.metric("Frauenquote", f"{quote} %", delta=f"{quote - 50:.1f} % zur Parität")

    st.divider()

    # ── Diagramme ──
    if show_ausschuss:
        st.subheader("Geschlechterverteilung pro Ausschuss")
        st.altair_chart(chart_ausschuesse(df_f), use_container_width=True)

    if show_rollen:
        st.subheader("Geschlechterverteilung nach Rolle")
        st.altair_chart(chart_rollen(df_f), use_container_width=True)

    if show_heatmap:
        st.subheader("Heatmap: Ausschuss × Rolle × Geschlecht")
        hm = chart_heatmap(df_f)
        if hm:
            st.altair_chart(hm, use_container_width=True)

    if show_quote:
        st.subheader("📋 Frauenquoten-Ranking nach Ausschuss")
        tbl = frauenquoten_tabelle(df_f)
        st.dataframe(
            tbl,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Quote (%)": st.column_config.ProgressColumn(
                    "Quote (%)", min_value=0, max_value=100, format="%.1f %%"
                )
            },
        )

    st.divider()

    # ── Rohdaten + Export ──
    with st.expander("📄 Rohdaten anzeigen / exportieren"):
        st.dataframe(df_f, use_container_width=True)
        csv = df_f.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ CSV herunterladen (für NotebookLM etc.)",
            data=csv,
            file_name=f"grevenbroich_{selected_term_name.replace(' ', '_')}.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
