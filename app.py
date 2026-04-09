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
    if not x:
        return None
    return x.strip().lower().replace("http://", "https://")


def fetch_all(url, label="Daten", limit_pages=50):
    """Lädt alle Seiten einer OParl-Resource mit Retry."""
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
                    st.error(f"Fehler beim Laden von {label} (Seite {page_count+1}): {e}")
                    bar.empty()
                    return all_items
                time.sleep(2)

        all_items.extend(data.get("data", []))
        url = data.get("links", {}).get("next")
        page_count += 1
        bar.progress(min(page_count / limit_pages, 1.0),
                     text=f"Lade {label}… ({len(all_items)} Einträge)")

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
def fetch_terms():
    resp = requests.get(f"{BASE_URL}/legislativeterms", timeout=20)
    resp.raise_for_status()
    raw = resp.json()
    if isinstance(raw, list):
        return raw
    return raw.get("data", raw.get("legislativeTerm", []))


# ─────────────────────────────────────────────
# KERN-LOGIK
# ─────────────────────────────────────────────

def build_dataframe_from_orgs(orgs, person_map, term_start, term_end):
    """
    Baut den DataFrame auf, indem Memberships direkt aus den
    Organisations-Objekten gelesen werden – nicht über den
    /memberships-Endpunkt, der paging-bedingt unvollständig sein kann.

    Jedes Organisations-Objekt enthält ein 'membership'-Array mit URLs
    zu allen Membership-Objekten dieses Gremiums. Wir rufen diese
    einzeln ab, um vollständige Daten zu erhalten.
    """
    rows = []

    # Nur Organisationen der gewählten Wahlperiode
    active_orgs = []
    for o in orgs:
        sd = o.get("startDate")
        if not sd:
            continue
        try:
            org_start = datetime.fromisoformat(sd[:10])
        except Exception:
            continue
        if term_start <= org_start <= term_end:
            active_orgs.append(o)

    if not active_orgs:
        return pd.DataFrame()

    total_orgs = len(active_orgs)
    bar = st.progress(0, text="Lade Mitgliedschaften der Gremien…")

    for i, org in enumerate(active_orgs):
        org_name = org.get("name", "Unbekannt")
        membership_entries = org.get("membership", [])

        for m_entry in membership_entries:
            if isinstance(m_entry, str):
                # URL → einzeln abrufen
                for attempt in range(3):
                    try:
                        resp = requests.get(m_entry, timeout=20)
                        resp.raise_for_status()
                        m = resp.json()
                        break
                    except Exception:
                        if attempt == 2:
                            m = None
                        time.sleep(1)
                if not m:
                    continue
            elif isinstance(m_entry, dict):
                m = m_entry
            else:
                continue

            pid = normalize_id(m.get("person"))
            name, gender = person_map.get(pid, ("Unbekannt", "Unbekannt"))

            rows.append({
                "Person":     name,
                "Geschlecht": gender,
                "Rolle":      m.get("role", "Unbekannt"),
                "Ausschuss":  org_name,
                "StartDatum": m.get("startDate", ""),
            })

        bar.progress(
            (i + 1) / total_orgs,
            text=f"Lade Mitgliedschaften… {i+1}/{total_orgs}: {org_name}",
        )

    bar.empty()
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# VISUALISIERUNGEN
# ─────────────────────────────────────────────

GENDER_COLORS = alt.Scale(
    domain=["weiblich", "männlich", "divers", "Unbekannt"],
    range=["#e63946", "#457b9d", "#2a9d8f", "#aaa"],
)


def chart_ausschuesse(df):
    df_agg = df.groupby(["Ausschuss", "Geschlecht"]).size().reset_index(name="Anzahl")
    return (
        alt.Chart(df_agg)
        .mark_bar()
        .encode(
            x=alt.X("Ausschuss:N", sort="-y", title="Ausschuss"),
            y=alt.Y("Anzahl:Q"),
            color=alt.Color("Geschlecht:N", scale=GENDER_COLORS),
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
            color=alt.Color("Geschlecht:N", scale=GENDER_COLORS),
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
                x=alt.X("Ausschuss:N"),
                y=alt.Y("Rolle:N"),
                color=alt.Color("Anzahl:Q", scale=alt.Scale(scheme="reds")),
                tooltip=["Ausschuss", "Rolle", "Anzahl"],
            )
            .properties(title=g, width=220, height=300)
        )
        charts.append(c)
    return alt.hconcat(*charts) if charts else None


def frauenquoten_tabelle(df):
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
    tbl["⚠️"] = tbl["Quote (%)"].apply(lambda q: "🔴 unter 30 %" if q < 30 else "✅")
    return tbl.reset_index()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    st.set_page_config(page_title="Grevenbroich – Mitgliederanalyse", layout="wide")
    st.title("🏛️ Stadt Grevenbroich – Mitgliederanalyse")
    st.caption(
        "Datenquelle: [OParl Grevenbroich](https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013)"
    )

    # ── Stammdaten laden ──
    with st.spinner("Lade Stammdaten…"):
        people = fetch_people()
        orgs   = fetch_orgs()
        terms  = fetch_terms()

    # ── Wahlperiode wählen ──
    valid_terms = sorted(
        [t for t in terms if t.get("startDate") and t.get("name")],
        key=lambda x: x["startDate"],
        reverse=True,
    )
    term_names = [t["name"] for t in valid_terms]

    selected_term_name = st.sidebar.selectbox("Wahlperiode", term_names, index=0)
    selected_term = next(t for t in valid_terms if t["name"] == selected_term_name)

    term_start = datetime.fromisoformat(selected_term["startDate"])
    term_end   = datetime.fromisoformat(
        selected_term.get("endDate", datetime.now().date().isoformat())
    )
    st.sidebar.caption(f"{term_start.date()} – {term_end.date()}")

    # ── Personen-Map ──
    person_map = {
        normalize_id(p["id"]): (p.get("name", "Unbekannt"), p.get("gender", "Unbekannt"))
        for p in people
    }

    # ── DataFrame bauen ──
    st.info(
        "💡 Memberships werden direkt aus jedem Gremium geladen – "
        "das dauert beim ersten Mal etwas länger, liefert dafür vollständige Zahlen."
    )
    df = build_dataframe_from_orgs(orgs, person_map, term_start, term_end)

    if df.empty:
        st.warning(
            f"Keine Daten für **{selected_term_name}** gefunden. "
            "Die Organisationen haben möglicherweise noch kein startDate in dieser Periode."
        )
        return

    st.sidebar.success(f"✅ {len(df)} Mitgliedschaften geladen")

    # ── Sidebar Filter ──
    st.sidebar.header("🔍 Filter")

    ausschuss_filter = st.sidebar.multiselect(
        "Ausschuss",
        sorted(df["Ausschuss"].unique()),
        default=sorted(df["Ausschuss"].unique()),
    )
    rollen_filter = st.sidebar.multiselect(
        "Rolle",
        sorted(df["Rolle"].unique()),
        default=sorted(df["Rolle"].unique()),
    )
    gender_filter = st.sidebar.multiselect(
        "Geschlecht",
        sorted(df["Geschlecht"].unique()),
        default=sorted(df["Geschlecht"].unique()),
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
    total   = len(df_f)
    frauen  = (df_f["Geschlecht"] == "weiblich").sum()
    maenner = (df_f["Geschlecht"] == "männlich").sum()
    quote   = round(frauen / total * 100, 1) if total > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mitgliedschaften gesamt", total)
    col2.metric("Frauen", frauen)
    col3.metric("Männer", maenner)
    col4.metric("Frauenquote", f"{quote} %",
                delta=f"{quote - 50:.1f} % zur Parität",
                delta_color="normal")

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
