import requests

def fetch_all(url):
    """Alle Seiten einer OParl-Resource laden."""
    all_items = []
    while url:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", [])
        all_items.extend(items)
        url = data.get("links", {}).get("next")  # OParl paging: next link
    return all_items

# Beispielaufrufe
memberships = fetch_all("https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/memberships")
people = fetch_all("https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/people")
organizations = fetch_all("https://ris-oparl.itk-rheinland.de/Oparl/bodies/0013/organizations")
