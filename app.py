import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(page_title="Grevenbroich Ausschüsse", layout="wide")

BASE_URL = "https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013"

@st.cache_data
def load_data():
    people = requests.get(f"{BASE_URL}/people").json()['data']
    memberships = requests.get(f"{BASE_URL}/memberships").json()['data']
    orgs = requests.get(f"{BASE_URL}/organizations").json()['data']

    df_people = pd.DataFrame(people)
    df_memberships = pd.DataFrame(memberships)
    df_orgs = pd.DataFrame(orgs)

    # IDs extrahieren
    df_people['person_id'] = df_people['id'].str.split('/').str[-1]
    df_memberships['person_id'] = df_memberships['person'].str.split('/').str[-1]
    df_memberships['org_id'] = df_memberships['organization'].str.split('/').str[-1]
    df_orgs['org_id'] = df_orgs['id'].str.split('/').str[-1]

    # Mergen
    df = df_memberships.merge(df_people, on="person_id")
    df = df.merge(df_orgs[['org_id', 'name']], on="org_id")

    df.rename(columns={"name": "ausschuss"}, inplace=True)

    return df

df = load_data()

st.title("📊 Geschlechterverteilung in Ausschüssen (Grevenbroich)")

# Filter
ausschuesse = st.multiselect(
    "Ausschüsse auswählen",
    options=sorted(df["ausschuss"].unique()),
    default=sorted(df["ausschuss"].unique())
)

filtered_df = df[df["ausschuss"].isin(ausschuesse)]

# Aggregation
result = (
    filtered_df
    .groupby(["ausschuss", "gender"])
    .size()
    .reset_index(name="anzahl")
)

# Diagramm
fig = px.bar(
    result,
    x="ausschuss",
    y="anzahl",
    color="gender",
    title="Verteilung nach Geschlecht"
)

st.plotly_chart(fig, use_container_width=True)

# Frauenanteil berechnen
pivot = result.pivot(index="ausschuss", columns="gender", values="anzahl").fillna(0)

if "female" in pivot.columns:
    pivot["frauenanteil"] = pivot["female"] / pivot.sum(axis=1)
else:
    pivot["frauenanteil"] = 0

pivot = pivot.sort_values("frauenanteil")

st.subheader("📉 Ranking nach Frauenanteil")

st.dataframe(
    pivot.style.format({"frauenanteil": "{:.1%}"})
)

# Highlight
st.subheader("⚠️ Auffällige Ausschüsse")

low = pivot[pivot["frauenanteil"] < 0.3]

if not low.empty:
    st.warning("Ausschüsse mit weniger als 30% Frauenanteil:")
    st.write(low)
else:
    st.success("Keine stark unausgewogenen Ausschüsse gefunden")
