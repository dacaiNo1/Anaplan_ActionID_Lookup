import base64
import ssl
import time
import requests
import streamlit as st
import pandas as pd

# ---- SSL BYPASS (if needed for local certificate issues) ----
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
requests.packages.urllib3.disable_warnings()

# ---- CONSTANTS ----
BASE_URL = "https://api.anaplan.com/1/3"
CREDENTIAL_EXPIRY_SECONDS = 600  # 10 minutes


# ---- AUTH ----
def get_basic_auth_header(username, password):
    """
    Returns a Basic Auth header as per Anaplan API.
    """
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    return f"Basic {encoded}"


# ---- CREDENTIAL HANDLING ----
def save_credentials(email, password):
    st.session_state["credentials"] = {
        "email": email,
        "password": password,
        "timestamp": time.time()
    }


def get_credentials():
    creds = st.session_state.get("credentials")
    if creds and (time.time() - creds["timestamp"]) < CREDENTIAL_EXPIRY_SECONDS:
        return creds["email"], creds["password"]
    return None, None


def credential_form():
    stored_email, stored_password = get_credentials()

    st.subheader("🔐 Anaplan Credentials")
    email = st.text_input("Email", value=stored_email or "")
    password = st.text_input("Password", type="password", value=stored_password or "")

    if st.button("💾 Save Credentials (10 min)"):
        save_credentials(email, password)
        st.success("✅ Credentials saved for 10 minutes.")

    return email, password


# ---- FETCH ----
def fetch_items(auth_header, workspace_id, model_id, item_type):
    url = f"{BASE_URL}/workspaces/{workspace_id}/models/{model_id}/{item_type}"
    headers = {"Authorization": auth_header}
    response = requests.get(url, headers=headers, verify=False)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                return value
        return []
    elif isinstance(data, list):
        return data
    else:
        return []


def get_all_action_types(auth_header, workspace_id, model_id):
    return {
        "Processes": fetch_items(auth_header, workspace_id, model_id, "processes"),
        "Imports": fetch_items(auth_header, workspace_id, model_id, "imports"),
        "Exports": fetch_items(auth_header, workspace_id, model_id, "exports"),
        "Other Actions": fetch_items(auth_header, workspace_id, model_id, "actions")
    }


# ---- STREAMLIT APP ----
def main():
    st.set_page_config(page_title="Anaplan Actions Lookup", layout="centered")
    st.title("🔍 Anaplan Actions Lookup Tool")

    if "auth_header" not in st.session_state:
        st.session_state.auth_header = None
    if "action_data" not in st.session_state:
        st.session_state.action_data = None
    if "workspace_id" not in st.session_state:
        st.session_state.workspace_id = ""
    if "model_id" not in st.session_state:
        st.session_state.model_id = ""

    # ---- Credentials Section ----
    email, password = credential_form()
    workspace_id = st.text_input("Workspace ID", value=st.session_state.workspace_id)
    model_id = st.text_input("Model ID", value=st.session_state.model_id)

    if st.button("Fetch Actions"):
        if not email or not password:
            st.error("Please enter and save your credentials first.")
        elif not workspace_id or not model_id:
            st.error("Please enter Workspace ID and Model ID.")
        else:
            try:
                auth_header = get_basic_auth_header(email, password)
                st.session_state.auth_header = auth_header
                st.session_state.workspace_id = workspace_id
                st.session_state.model_id = model_id

                with st.spinner("Fetching all action categories..."):
                    action_data = get_all_action_types(auth_header, workspace_id, model_id)
                    st.session_state.action_data = action_data

                    if not any(action_data.values()):
                        st.warning("No actions found in the model.")
                    else:
                        st.success("✅ Actions loaded successfully!")
            except Exception as e:
                st.error(f"Connection Error: {str(e)}")

    # ---- Display Actions ----
    if st.session_state.action_data:
        st.divider()
        combined_data = []
        for category, items in st.session_state.action_data.items():
            st.subheader(f"📋 {category}")
            if items:
                df = pd.DataFrame([{"Name": i.get("name", ""), "ID": i.get("id", "")} for i in items])
                st.table(df)

                # Add to combined list
                for row in df.to_dict(orient="records"):
                    row["Type"] = category
                    combined_data.append(row)
            else:
                st.info(f"No {category.lower()} found.")

        # Combined CSV
        if combined_data:
            combined_df = pd.DataFrame(combined_data)
            st.subheader("📥 Download All Actions (Combined)")
            csv_data = combined_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Combined CSV",
                data=csv_data,
                file_name="anaplan_all_actions.csv",
                mime="text/csv"
            )


if __name__ == "__main__":
    main()
