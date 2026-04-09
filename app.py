"""
Grevenbroich Mitgliederanalyse
==============================

DATENMODELL (nach API-Analyse):
- /organizations  → Liste aller Gremien, jedes enthält ein 'membership'-Array
                    mit den URLs aller zugehörigen Memberships.
                    Das 'startDate' der Organisation ist NICHT zuverlässig
                    für Wahlperioden-Filterung.
- /people         → Personen mit Name, Geschlecht, gender
- /memberships    → Membership-Objekte: person-URL, organization-URL, role,
                    startDate, votingRight

STRATEGIE:
1. Alle Organisationen laden (alle Seiten).
2. Alle Personen laden (alle Seiten).
3. Memberships NICHT über /memberships laden (Paging-Reihenfolge unzuverlässig).
   Stattdessen: Pro Organisation die membership-URLs direkt aus dem Org-Objekt
   nehmen und die Membership-Objekte einzeln abrufen.
4. Filter nach Wahlperiode über das startDate der MEMBERSHIP (nicht der Org).
"""

import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013"

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def normalize_id(x):
    if not x:
        return None
    return x.strip().lower().replace("http://", "https://")


def get_json(url, retries=3, timeout=20):
    """Einzelner robuster GET-Request."""
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                return None
            time.sleep(1.5)
    return None


def fetch_all_pages(url, label=""):
    """
    Lädt ALLE Seiten einer OParl-Liste ohne künstliches Limit.
    Zeigt Fortschritt in der Streamlit-UI.
    """
    all_items = []
    page = 1
    placeholder = st.empty()

    while url:
        data = get_json(url)
        if data is None:
            placeholder.error(f"Fehler beim Laden von {label} Seite {page}")
            break

        batch = data.get("data", [])
        all_items.extend(batch)
        placeholder.info(f"Lade {label}… {len(all_items)} Einträge (Seite {page})")

        url = data.get("links", {}).get("next")
        page += 1

    placeholder.empty()
    return all_items


# ─────────────────────────────────────────────
# CACHED FETCHES
# ─────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def fetch_people():
    return fetch_all_pages(f"{BASE_URL}/people", "Personen")


@st.cache_data(show_spinner=False)
def fetch_orgs():
    return fetch_all_pages(f"{BASE_URL}/organizations", "Organisationen")


@st.cache_data(show_spinner=False)
def fetch_terms():
    raw = get_json(f"{BASE_URL}/legislativeterms")
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    # Grevenbroich liefert Terms im Body-Objekt unter 'legislativeTerm'
    return raw.get("data", raw.get("legislativeTerm", []))


@st.cache_data(show_spinner=False)
def fetch_membership(url: str):
    """Lädt ein einzelnes Membership-Objekt (gecacht per URL)."""
    return get_json(url)


# ─────────────────────────────────────────────
# KERN-LOGIK
# ─────────────────────────────────────────────

def load_all_memberships_from_orgs(orgs: list) -> list:
    """
    Sammelt alle Membership-URLs aus allen Organisations-Objekten
    und lädt sie parallel.

    Warum dieser Ansatz:
    - /memberships-Endpunkt liefert Daten absteigend nach ID → ältere
      Memberships (niedrige IDs wie 6151) kommen auf späten Seiten.
    - Organisationen enthalten ihr komplettes membership[]-Array direkt.
    - Wir laden jede Membership-URL einmal (dedupliziert).
    """
    # Alle einzigartigen Membership-URLs sammeln
    all_urls = set()
    for org in orgs:
        for entry in org.get("membership", []):
            if isinstance(entry, str):
                all_urls.add(entry.strip())

    all_urls = list(all_urls)
    total = len(all_urls)

    if total == 0:
        return []

    bar = st.progress(0, text=f"Lade {total} Membership-Objekte…")
    results = []
    done = 0

    # Parallel laden mit 10 Threads für akzeptable Geschwindigkeit
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_membership, url): url for url in all_urls}
        for future in as_completed(futures):
            m = future.result()
            if m and isinstance(m, dict) and "person" in m:
                results.append(m)
            done += 1
            if done % 10 == 0 or done == total:
                bar.progress(done / total,
                             text=f"Lade Memberships… {done}/{total}")

    bar.empty()
    return results


def build_dataframe(memberships: list, person_map: dict, org_map: dict,
                    term_start: datetime, term_end: datetime) -> pd.DataFrame:
    """
    Baut den DataFrame auf.
    Filter nach Wahlperiode: startDate der MEMBERSHIP liegt im Zeitraum.
    """
    rows = []
    skipped = 0

    for m in memberships:
        # Zeitfilter über Membership-startDate
        sd = m.get("startDate", "")
        if sd:
            try:
                start = datetime.fromisoformat(sd[:10])
                if not (term_start <= start <= term_end):
                    skipped += 1
                    continue
            except Exception:
                pass

        pid = normalize_id(m.get("person"))
        oid = normalize_id(m.get("organization"))
        name, gender = person_map.get(pid, ("Unbekannt", "Unbekannt"))
        org_name = org_map.get(oid, "Unbekannt")

        rows.append({
            "Person":     name,
            "Geschlecht": gender,
            "Rolle":      m.get("role", "Unbekannt"),
            "Ausschuss":  org_name,
            "StartDatum": sd[:10] if sd else "",
            "Stimmrecht": "Ja" if m.get("votingRight") else "Nein",
        })

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
        alt.Chart(df_agg).mark_bar()
        .encode(
            x=alt.X("Ausschuss:N", sort="-y", axis=alt.Axis(labelAngle=-40)),
            y="Anzahl:Q",
            color=alt.Color("Geschlecht:N", scale=GENDER_COLORS),
            tooltip=["Ausschuss", "Geschlecht", "Anzahl"],
        )
        .properties(height=400)
    )


def chart_rollen(df):
    df_agg = df.groupby(["Rolle", "Geschlecht"]).size().reset_index(name="Anzahl")
    return (
        alt.Chart(df_agg).mark_bar()
        .encode(
            x=alt.X("Rolle:N", sort="-y", axis=alt.Axis(labelAngle=-30)),
            y="Anzahl:Q",
            color=alt.Color("Geschlecht:N", scale=GENDER_COLORS),
            tooltip=["Rolle", "Geschlecht", "Anzahl"],
        )
        .properties(height=350)
    )


def chart_heatmap(df):
    df_agg = (
        df.groupby(["Ausschuss", "Rolle", "Geschlecht"])
        .size().reset_index(name="Anzahl")
    )
    charts = []
    for g in sorted(df_agg["Geschlecht"].unique()):
        dfg = df_agg[df_agg["Geschlecht"] == g]
        charts.append(
            alt.Chart(dfg).mark_rect()
            .encode(
                x=alt.X("Ausschuss:N", axis=alt.Axis(labelAngle=-40)),
                y="Rolle:N",
                color=alt.Color("Anzahl:Q", scale=alt.Scale(scheme="reds")),
                tooltip=["Ausschuss", "Rolle", "Anzahl"],
            )
            .properties(title=g, width=220, height=300)
        )
    return alt.hconcat(*charts) if charts else None


def frauenquoten_tabelle(df):
    total  = df.groupby("Ausschuss").size().rename("Gesamt")
    frauen = df[df["Geschlecht"] == "weiblich"].groupby("Ausschuss").size().rename("Frauen")
    tbl = pd.concat([total, frauen], axis=1).fillna(0)
    tbl["Frauen"] = tbl["Frauen"].astype(int)
    tbl["Quote (%)"] = (tbl["Frauen"] / tbl["Gesamt"] * 100).round(1)
    tbl["⚠️"] = tbl["Quote (%)"].apply(lambda q: "🔴 unter 30 %" if q < 30 else "✅")
    return tbl.sort_values("Quote (%)").reset_index()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    st.set_page_config(page_title="Grevenbroich – Mitgliederanalyse", layout="wide")
    st.title("🏛️ Stadt Grevenbroich – Mitgliederanalyse")
    st.caption("Datenquelle: [OParl Grevenbroich](https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013)")

    # ── Stammdaten ──
    with st.spinner("Lade Personen, Organisationen und Wahlperioden…"):
        people = fetch_people()
        orgs   = fetch_orgs()
        terms  = fetch_terms()

    # ── Wahlperiode wählen ──
    valid_terms = sorted(
        [t for t in terms if t.get("startDate") and t.get("name")],
        key=lambda x: x["startDate"], reverse=True,
    )
    term_names = [t["name"] for t in valid_terms]

    st.sidebar.header("⚙️ Einstellungen")
    selected_name = st.sidebar.selectbox("Wahlperiode", term_names, index=0)
    sel = next(t for t in valid_terms if t["name"] == selected_name)

    term_start = datetime.fromisoformat(sel["startDate"])
    term_end   = datetime.fromisoformat(
        sel.get("endDate", datetime.now().date().isoformat())
    )
    st.sidebar.caption(f"{term_start.date()} – {term_end.date()}")

    # ── Memberships laden (aus Organisations-Objekten) ──
    memberships = load_all_memberships_from_orgs(orgs)

    if not memberships:
        st.error("Keine Membership-Daten geladen. Bitte Seite neu laden.")
        return

    # ── Maps aufbauen ──
    person_map = {
        normalize_id(p["id"]): (p.get("name", "Unbekannt"), p.get("gender", "Unbekannt"))
        for p in people
    }
    org_map = {
        normalize_id(o["id"]): o.get("name", "Unbekannt")
        for o in orgs
    }

    # ── DataFrame ──
    df = build_dataframe(memberships, person_map, org_map, term_start, term_end)

    if df.empty:
        st.warning(
            f"Keine Mitgliedschaften für **{selected_name}** gefunden.\n\n"
            f"Gesamte Memberships geladen: {len(memberships)}. "
            "Überprüfe ob die startDate-Werte der Memberships in diesen Zeitraum fallen."
        )
        # Debug-Hilfe: zeige alle startDates der geladenen Memberships
        with st.expander("🔍 Debug: StartDaten aller Memberships"):
            dates = sorted(set(
                m.get("startDate", "")[:10] for m in memberships if m.get("startDate")
            ))
            st.write(f"Gefundene startDate-Werte ({len(dates)} verschiedene):")
            st.write(dates)
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

    st.sidebar.header("📊 Ansicht")
    show_ausschuss = st.sidebar.checkbox("Ausschüsse", True)
    show_rollen    = st.sidebar.checkbox("Rollen", True)
    show_heatmap   = st.sidebar.checkbox("Heatmap", True)
    show_quote     = st.sidebar.checkbox("Frauenquoten-Ranking", True)

    df_f = df[
        df["Ausschuss"].isin(ausschuss_filter) &
        df["Rolle"].isin(rollen_filter) &
        df["Geschlecht"].isin(gender_filter)
    ]

    # ── KPIs ──
    total   = len(df_f)
    frauen  = (df_f["Geschlecht"] == "weiblich").sum()
    maenner = (df_f["Geschlecht"] == "männlich").sum()
    unbekannt = (df_f["Geschlecht"] == "Unbekannt").sum()
    quote   = round(frauen / total * 100, 1) if total > 0 else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Mitgliedschaften", total)
    c2.metric("Frauen", frauen)
    c3.metric("Männer", maenner)
    c4.metric("Unbekannt", unbekannt)
    c5.metric("Frauenquote", f"{quote} %", delta=f"{quote-50:.1f} % zur Parität")

    st.divider()

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
        st.dataframe(
            frauenquoten_tabelle(df_f),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Quote (%)": st.column_config.ProgressColumn(
                    "Quote (%)", min_value=0, max_value=100, format="%.1f %%"
                )
            },
        )

    st.divider()

    with st.expander("📄 Rohdaten / CSV-Export"):
        st.dataframe(df_f, use_container_width=True)
        st.download_button(
            "⬇️ CSV herunterladen",
            data=df_f.to_csv(index=False).encode("utf-8"),
            file_name=f"grevenbroich_{selected_name.replace(' ', '_')}.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
