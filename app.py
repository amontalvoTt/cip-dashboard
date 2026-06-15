import streamlit as st
import pandas as pd
import numpy as np
import io
import plotly.express as px
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium
from folium.plugins import MarkerCluster

st.set_page_config(layout="wide", page_title="Enterprise CIP Prioritization Dashboard")

st.title("🗺️ Interactive Capital Improvement Planning (CIP) Dashboard")
st.markdown("---")

# --- 1. DATA LOADING & INGESTION ---
st.sidebar.header("1. Data Ingestion")
uploaded_file = st.sidebar.file_uploader("Upload CIP Table (CSV)", type=["csv"])

# Text score mapper for Sheet 2 variations
score_map = {"Low": 1, "Medium": 3, "High": 5, "No": 1, "Yes": 5}

def clean_and_normalize(df):
    # Detect Schema Type
    if 'Asset_Category' in df.columns:
        # Sheet 1 Schema
        df['Clean_Cost'] = pd.to_numeric(df['Capital_Cost'], errors='coerce').fillna(0)
        df['Start_Dt'] = pd.to_datetime(df['Project_Start_Date'], errors='coerce')
        df['End_Dt'] = pd.to_datetime(df['Project_End_Date'], errors='coerce')
        df['Dept'] = df['Department']
        
        # Standardize criteria scores (already numeric in sheet 1)
        score_cols = {
            'Flood': pd.to_numeric(df['Flood_Mitigation_Score'], errors='coerce').fillna(1),
            'Sustain': pd.to_numeric(df['Sustainability_Score'], errors='coerce').fillna(1),
            'Econ': pd.to_numeric(df['Economic_Impact_Score'], errors='coerce').fillna(1),
            'Equity': pd.to_numeric(df['Social_Justice_Equity_Score'], errors='coerce').fillna(1),
            'Risk': pd.to_numeric(df['Risk_Mitigation_Score'], errors='coerce').fillna(1)
        }
    else:
        # Sheet 2 Schema
        df['Clean_Cost'] = pd.to_numeric(df['Capital_Cost'], errors='coerce').fillna(0)
        df['Start_Dt'] = pd.to_datetime(df['Start_Date'], errors='coerce')
        df['End_Dt'] = pd.to_datetime(df['End_Date'], errors='coerce')
        df['Dept'] = df['Department']
        
        # Standardize and map text criteria rankings
        score_cols = {
            'Flood': df['Flood_Mitigation'].map(score_map).fillna(1),
            'Sustain': df['Sustainability'].map(score_map).fillna(1),
            'Econ': df['Economic_Impact'].map(score_map).fillna(1),
            'Equity': df['Social_Equity'].map(score_map).fillna(1),
            'Risk': df['Risk_Mitigation'].map(score_map).fillna(1)
        }
    
    for k, v in score_cols.items():
        df[f'score_{k}'] = v
        
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    return df.dropna(subset=['Start_Dt', 'End_Dt'])

if uploaded_file is not None:
    # Read the file contents as raw text first to strip out any problematic source tags
    try:
        raw_bytes = uploaded_file.read()
        # Decode using utf-8-sig to clear Excel BOMs automatically
        raw_text = raw_bytes.decode('utf-8-sig', errors='ignore')
    except Exception:
        # Fallback decode if it's a legacy Windows export
        raw_text = raw_bytes.decode('cp1252', errors='ignore')
        
    # Clean out the copy-paste markdown tags so they don't break row alignments
    import re
    cleaned_text = re.sub(r'\', '', raw_text)
    
    # Pass the cleaned text stream into pandas using the flexible Python parsing engine
    try:
        raw_df = pd.read_csv(
            io.StringIO(cleaned_text), 
            engine='python', 
            on_bad_lines='skip'  # Safely bypasses rows that are fundamentally broken
        )
        df = clean_and_normalize(raw_df)
    except Exception as e:
        st.error(# Forced fallback if everything else fails
            f"Failed to parse CSV file structure. Technical details: {str(e)}"
        )
else:
    st.info("💡 Please upload a CIP CSV file to initialize. Awaiting data input...")
    st.stop()


# --- 2. DYNAMIC SCORING ENGINE ---
st.sidebar.header("2. Prioritization Weights")
w_flood = st.sidebar.slider("Flood Mitigation Weight", 0.0, 1.0, 0.2)
w_sustain = st.sidebar.slider("Sustainability Weight", 0.0, 1.0, 0.2)
w_econ = st.sidebar.slider("Economic Impact Weight", 0.0, 1.0, 0.2)
w_equity = st.sidebar.slider("Social Equity / Justice Weight", 0.0, 1.0, 0.2)
w_risk = st.sidebar.slider("Risk Mitigation Weight", 0.0, 1.0, 0.2)

# Calculate Normalized Weighted Score
df['Custom_Priority_Score'] = (
    (df['score_Flood'] * w_flood) +
    (df['score_Sustain'] * w_sustain) +
    (df['score_Econ'] * w_econ) +
    (df['score_Equity'] * w_equity) +
    (df['score_Risk'] * w_risk)
)
df['Custom_Priority_Score'] = df['Custom_Priority_Score'].round(2)
df = df.sort_values(by='Custom_Priority_Score', ascending=False)

# --- 3. CASH FLOW TEMPORAL SPREADING ---
cash_flow_records = []
for idx, row in df.iterrows():
    days = (row['End_Dt'] - row['Start_Dt']).days
    if days <= 0:
        days = 1
    daily_cost = row['Clean_Cost'] / days
    
    # Generate daily sequence and assign to calendar year bins
    date_range = pd.date_range(start=row['Start_Dt'], end=row['End_Dt'], freq='D')
    for d in date_range:
        cash_flow_records.append({
            'CIP_ID': row['CIP_ID'],
            'Project_Name': row['Project_Name'],
            'Department': row['Dept'],
            'Year': d.year,
            'Daily_Cost': daily_cost
        })

cf_df = pd.DataFrame(cash_flow_records)
annual_cf = cf_df.groupby(['Year', 'Department'])['Daily_Cost'].sum().reset_index()
annual_cf.rename(columns={'Daily_Cost': 'Annual_Expenditure'}, inplace=True)

# Generate Cumulative Metrics
cumulative_df = cf_df.groupby('Year')['Daily_Cost'].sum().cumsum().reset_index()
cumulative_df.rename(columns={'Daily_Cost': 'Cumulative_Expenditure'}, inplace=True)

# --- 4. DASHBOARD LAYOUT & VISUALS ---
col1, col2 = pd.columns([3, 2])

with col1:
    st.subheader("📍 Geospatial Project Inventory (Leaflet)")
    
    # Initialize Map around Centroid
    mid_lat = df['Latitude'].dropna().median() if not df['Latitude'].isna().all() else 28.5383
    mid_lon = df['Longitude'].dropna().median() if not df['Longitude'].isna().all() else -81.3792
    
    m = folium.Map(location=[mid_lat, mid_lon], zoom_start=10, tiles="cartodbpositron")
    marker_cluster = MarkerCluster().add_to(m)
    
    for idx, row in df.dropna(subset=['Latitude', 'Longitude']).iterrows():
        popup_text = f"""
        <b>ID:</b> {row['CIP_ID']}<br>
        <b>Name:</b> {row['Project_Name']}<br>
        <b>Dept:</b> {row['Dept']}<br>
        <b>Cost:</b> ${row['Clean_Cost']:,.0f}<br>
        <b>Score:</b> {row['Custom_Priority_Score']}
        """
        # Color nodes based on priority tiering
        score = row['Custom_Priority_Score']
        node_color = 'red' if score > 3.5 else 'orange' if score > 2.2 else 'green'
        
        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=7,
            color=node_color,
            fill=True,
            fill_color=node_color,
            fill_opacity=0.7,
            popup=folium.Popup(popup_text, max_width=300)
        ).add_to(marker_cluster)
        
    st_folium(m, width="100%", height=450, returned_objects=[])

with col2:
    st.subheader("🏆 Weighted Rank Optimization Table")
    st.dataframe(
        df[['CIP_ID', 'Project_Name', 'Dept', 'Clean_Cost', 'Custom_Priority_Score']],
        use_container_width=True,
        height=450,
        column_config={
            "Clean_Cost": pd.column_config.NumberColumn("Capital Cost", format="$%,.0f"),
            "Custom_Priority_Score": pd.column_config.ProgressColumn("Priority Score", min_value=0, max_value=5)
        }
    )

# --- 5. FINANCIAL CASH FLOW VISUALIZATIONS ---
st.markdown("---")
st.subheader("⏳ Multi-Year Capital Cash Flow Projections (Linear Cost Spreading)")

col3, col4 = pd.columns(2)

with col3:
    # Binned Annual Cash Flow Stacked by Department
    fig_bar = px.bar(
        annual_cf, 
        x='Year', 
        y='Annual_Expenditure', 
        color='Department',
        title="Annual Funding Allocations (By Operating Department)",
        labels={'Annual_Expenditure': 'Allocated Budget ($)', 'Year': 'Calendar Year'},
        text_auto='.2s'
    )
    fig_bar.update_layout(xaxis_type='category', barmode='stack')
    st.plotly_chart(fig_bar, use_container_width=True)

with col4:
    # Cumulative Line Curve over Time
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=cumulative_df['Year'], 
        y=cumulative_df['Cumulative_Expenditure'],
        mode='lines+markers',
        name='Cumulative Spending',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=8)
    ))
    fig_line.update_layout(
        title="Cumulative Capital Program Expenditure Profile",
        xaxis_title="Calendar Year",
        yaxis_title="Total Program Investment ($)",
        xaxis=dict(type='category')
    )
    st.plotly_chart(fig_line, use_container_width=True)
