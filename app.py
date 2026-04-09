from collections import defaultdict

def build_membership_index(people):
    """
    Baut Index: {org_id: {person_id: gender}}
    Nimmt pro Person & Gremium nur die neueste Membership
    """
    memberships_by_org = defaultdict(dict)

    for person in people:
        person_id = person.get("id")
        gender = person.get("gender", "unknown")

        memberships = person.get("membership", [])
        if not isinstance(memberships, list):
            memberships = [memberships]

        for m in memberships:
            if not isinstance(m, dict):
                continue

            org_id = m.get("organization")
            start = m.get("startDate", "")

            if not org_id:
                continue

            existing = memberships_by_org[org_id].get(person_id)

            # 👉 wichtigste Logik: nur neueste Membership behalten
            if not existing or start > existing.get("startDate", ""):
                memberships_by_org[org_id][person_id] = {
                    "gender": gender,
                    "startDate": start
                }

    return memberships_by_org


def count_members(org_id, membership_index):
    members = {'male': 0, 'female': 0, 'unknown': 0}

    persons = membership_index.get(org_id, {})

    for p in persons.values():
        gender = p["gender"]

        if gender in ['male', 'männlich', 'm']:
            members['male'] += 1
        elif gender in ['female', 'weiblich', 'f']:
            members['female'] += 1
        else:
            members['unknown'] += 1

    return members
