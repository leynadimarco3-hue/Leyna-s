import io
import hashlib
import secrets
from collections import Counter

import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="All-State Player Rankings", page_icon="🏑", layout="centered")
st.title("🏑 All-State Player Rankings")

try:
    db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    admin_hash = st.secrets["ADMIN_PASSWORD_HASH"]
except Exception:
    st.error("App is not configured. Check Streamlit Settings → Secrets.")
    st.stop()


def admin_ok(password):
    return secrets.compare_digest(hashlib.sha256(password.encode()).hexdigest(), admin_hash)


def get_names():
    return db.table("candidates").select("id,name").order("id").execute().data or []


def parse_names(upload):
    data = io.BytesIO(upload.getvalue())
    df = pd.read_csv(data) if upload.name.lower().endswith(".csv") else pd.read_excel(data)
    if df.empty:
        return []
    col = next((c for c in df.columns if str(c).strip().lower() in ("name", "player", "player name", "candidate")), df.columns[0])
    names = [str(x).strip() for x in df[col].dropna().tolist()]
    names = [x for x in names if x and x.lower() != "nan"]
    if len(names) != len(set(x.casefold() for x in names)):
        raise ValueError("Duplicate player names found. Add a school to distinguish them.")
    return names


page = st.query_params.get("view", "vote")

if page == "admin":
    st.subheader("Private organizer dashboard")
    password = st.text_input("Admin password", type="password")
    if not password:
        st.stop()
    if not admin_ok(password):
        st.error("Incorrect password")
        st.stop()
    try:
        settings = db.table("poll_settings").select("*").eq("id", 1).single().execute().data
        candidates = get_names()
    except Exception as e:
        st.error(f"Could not load admin data: {e}")
        st.stop()
    st.write(f"Voting: **{'Open' if settings['is_open'] else 'Closed'}**")
    if st.button("Close voting" if settings["is_open"] else "Reopen voting"):
        db.table("poll_settings").update({"is_open": not settings["is_open"]}).eq("id", 1).execute()
        st.rerun()

    st.subheader("Current player list")
    st.write(f"{len(candidates)} players loaded")
    if candidates:
        st.dataframe(pd.DataFrame({"Name": [c["name"] for c in candidates]}), hide_index=True, width="stretch")

    st.subheader("Upload candidate list")
    st.caption("Upload CSV or Excel. Replacing the list permanently clears previous votes.")
    uploaded = st.file_uploader("Choose spreadsheet", type=["csv", "xlsx"])
    if uploaded:
        try:
            names = parse_names(uploaded)
            st.write(f"{len(names)} names detected")
            st.dataframe(pd.DataFrame({"Name": names}), hide_index=True, width="stretch")
            confirmed = st.checkbox("I understand replacing the list permanently erases previous votes")
            if st.button("Replace candidate list", type="primary", disabled=not (names and confirmed)):
                db.rpc("replace_candidates", {"p_names": names}).execute()
                st.success("Player list replaced")
                st.rerun()
        except Exception as e:
            st.error(f"Upload failed: {e}")

    st.subheader("Current results")
    try:
        ballots = db.table("ballots").select("id").execute().data or []
        votes = db.table("ballot_rankings").select("ballot_id,candidate_id,rank").execute().data or []
        st.metric("Submitted ballots", len(ballots))
        n = len(candidates)
        counts = {c["id"]: {"Name": c["name"], "Points": 0, "First-place votes": 0, "Total rankings": 0} for c in candidates}
        for v in votes:
            if v["candidate_id"] in counts:
                item = counts[v["candidate_id"]]
                item["Points"] += n - v["rank"] + 1
                item["First-place votes"] += int(v["rank"] == 1)
                item["Total rankings"] += 1
        if counts:
            results = pd.DataFrame(counts.values()).sort_values(["Points", "First-place votes", "Name"], ascending=[False, False, True]).reset_index(drop=True)
            results.insert(0, "Position", range(1, len(results) + 1))
            st.dataframe(results, hide_index=True, width="stretch")
            st.download_button("Download results CSV", results.to_csv(index=False).encode(), "all_state_results.csv", "text/csv")
            st.caption("Scoring: first receives N points, second N−1, and last receives 1.")
    except Exception as e:
        st.error(f"Could not load results: {e}")
    st.info("Share the main app URL without ?view=admin. Keep your admin password secret.")

else:
    # This branch must always render the voting interface when players are loaded.
    try:
        settings = db.table("poll_settings").select("is_open").eq("id", 1).single().execute().data
        candidates = get_names()
    except Exception as e:
        st.error(f"Could not load voting data: {e}")
        st.stop()

    if not settings or not settings.get("is_open", False):
        st.info("Voting is currently closed.")
        st.stop()
    if not candidates:
        st.info("The organizer has not uploaded a player list yet.")
        st.stop()

    n = len(candidates)
    st.subheader("Rank the players")
    st.write(f"Rank all **{n} players**. Type **1** for your top player, **2** for your second choice, and so on through **{n}**. Each rank can be used only once.")
    st.caption("Anonymous ballot. All ranks are required.")

    # Text inputs have no increment/decrement buttons, unlike number_input.
    # Widgets are outside a form so duplicate warnings update immediately.
    ids = tuple(c["id"] for c in candidates)
    if st.session_state.get("ballot_candidate_ids") != ids:
        for k in list(st.session_state):
            if k.startswith("rank_entry_"):
                del st.session_state[k]
        st.session_state["ballot_candidate_ids"] = ids

    entries = {}
    for candidate in candidates:
        entries[candidate["id"]] = st.text_input(
            candidate["name"],
            key=f"rank_entry_{candidate['id']}",
            placeholder=f"Enter 1–{n}",
        ).strip()

    provided = [x for x in entries.values() if x]
    invalid = [x for x in provided if not x.isdecimal() or not (1 <= int(x) <= n)]
    numeric = [int(x) for x in provided if x.isdecimal() and 1 <= int(x) <= n]
    duplicate_ranks = sorted(x for x, count in Counter(numeric).items() if count > 1)
    missing = n - len(provided)

    if invalid:
        st.error(f"Ranks must be whole numbers between 1 and {n}.")
    if duplicate_ranks:
        st.error("Duplicate rank(s): " + ", ".join(map(str, duplicate_ranks)) + ". Give each player a different number.")
    if missing:
        st.info(f"{missing} player(s) still need a ranking.")
    valid = len(provided) == n and not invalid and not duplicate_ranks and set(numeric) == set(range(1, n + 1))
    if valid:
        st.success("All rankings are valid. Ready to submit.")

    if st.button("Submit anonymous ballot", type="primary", disabled=not valid):
        try:
            db.rpc("submit_ballot", {
                "p_candidate_ids": [c["id"] for c in candidates],
                "p_ranks": [int(entries[c["id"]]) for c in candidates],
            }).execute()
            st.success("Your anonymous ballot was submitted. Thank you!")
            st.balloons()
        except Exception:
            st.error("Ballot submission failed. Voting may have closed or the player list may have changed. Refresh and try again.")
