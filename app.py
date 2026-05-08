import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Data Insights Hub", layout="wide")

st.title("📊 Enterprise Data Insights Hub")
st.markdown("Welcome to the internal data portal. Ask anything about our users or operations.")

# In Step 1, this expects raw SQL. In Step 2, we will change the label and wire it to Claude.
user_input = st.text_input("Enter your SQL Query:", placeholder="SELECT * FROM users LIMIT 10")

if st.button("Run Query"):
    if user_input:
        with st.spinner("Executing..."):
            try:
                # Call our FastAPI backend
                response = requests.post(
                    "http://localhost:8000/execute",
                    json={"query": user_input}
                )

                if response.status_code == 200:
                    result = response.json()

                    st.subheader("Executed SQL:")
                    st.code(result["query"], language="sql")

                    st.subheader("Results:")
                    data = result.get("data", [])

                    if isinstance(data, list) and len(data) > 0:
                        # Display as a clean dataframe
                        df = pd.DataFrame(data)
                        st.dataframe(df, use_container_width=True)
                        st.caption(f"Returned {len(data)} rows.")
                    elif isinstance(data, dict):
                        st.success(f"Operation successful. Rows affected: {data.get('rows_affected', 0)}")
                    else:
                        st.info("Query executed successfully, but returned no rows.")

                else:
                    st.error(f"Error executing query: {response.json().get('detail')}")

            except requests.exceptions.ConnectionError:
                st.error("Could not connect to the backend. Is FastAPI running on port 8000?")
    else:
        st.warning("Please enter a query.")