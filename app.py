import streamlit as st
import pandas as pd
import numpy as np
import io
import os
import plotly.express as px
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium
from folium.plugins import MarkerCluster
# Page Configuration
st.set_page_config(layout="wide", page_title="Capital Improvement Planning (CIP) Dashboard")
st.title("🗺️ Interactive Capital Improvement Planning & Scoring Dashboard")
st.markdown("---")
# --- 1. DATA INGESTION & DATA CLEANING ENGINE ---
@st.cache_data
def load_and_clean_data(file_source):
   # Handle both file uploads (bytes/buffers) and local server paths seamlessly
   if isinstance(file_source, (str, os.PathLike)):
       df = pd.read_csv(file_source, encoding='utf-8-sig', engine='python', on_bad_lines='skip')
   else:
       # If it's a file uploader object, read it as raw text to parse cleanly
       raw_bytes = file_source.read()
       raw_text = raw_bytes.decode('utf-8-sig', errors='ignore')
       df = pd.read_csv(io.StringIO(raw_text), engine='python', on_bad_lines='skip')
   # Standardize and clean financial columns (stripping whitespace, quotes, commas, dollar signs)
   for col in ['Capital_Cost', 'Operating_Cost_Annual']:
       if col in df.columns:
           df[col] = df[col].astype(str).str.replace('$', '', regex=False)
           df[col] = df[col].str.replace(',', '', regex=False)
           df[col] = df[col].str.strip()
           df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
   # Force flexible date parsing to handle mixed format (e.g. 1/15/2026 or 2026-01-15)
   df['Start_Dt'] = pd.to_datetime(df['Project_Start_Date'], errors='coerce', format='mixed')
   df['End_Dt'] = pd.to_datetime(df['Project_End_Date'], errors='coerce', format='mixed')
   # Ensure coordinates are numeric
   df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
   df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
   # Fill missing criteria scores with neutral baseline
   score_cols = [
       'Flood_Mitigation_Score', 'Sustainability_Score', 'Economic_Impact_Score',
       'Social_Justice_Equity_Score', 'Risk_Mitigation_Score', 'Constructability_Score'
   ]
   for col in score_cols:
       if col in df.columns:
           df[col] = pd.to_numeric(df[col], errors='coerce').fillna(3)
   return df.dropna(subset=['Start_Dt', 'End_Dt'])
# Sidebar File Selection & Dynamic Cloud Directory Resolution
st.sidebar.header("📁 Data Source Selection")
uploaded_file = st.sidebar.file_uploader("Upload an updated CIP CSV file", type=["csv"])
df = None
# Attempt to locate the file dynamically regardless of directory context
default_filename = "CIP_Table.csv"
cloud_path = os.path.join(os.getcwd(), default_filename)
if uploaded_file is not None:
   try:
       df = load_and_clean_data(uploaded_file)
       st.sidebar.success("Successfully loaded uploaded CSV dataset.")
   except Exception as e:
       st.sidebar.error(f"Error parsing uploaded file: {str(e)}")
elif os.path.exists(default_filename):
   try:
       df = load_and_clean_data(default_filename)
       st.sidebar.success(f"Successfully loaded local baseline matrix ({len(df)} projects).")
   except Exception as e:
       st.sidebar.error(f"Error parsing local default file: {str(e)}")
elif os.path.exists(cloud_path):
   try:
       df = load_and_clean_data(cloud_path)
       st.sidebar.success(f"Successfully loaded cloud baseline matrix ({len(df)} projects).")
   except Exception as e:
       st.sidebar.error(f"Error parsing cloud default file: {str(e)}")
else:
   st.sidebar.warning("⚠️ Baseline file not found in repository root directory.")
# Halt layout initialization gracefully if data matrix is missing
if df is None or df.empty:
   st.info("💡 Please upload your project dataset (`CIP_Table.csv`) via the sidebar interface to initialize the application.")
   st.stop()
# --- 2. MULTI-CRITERIA SCORING & FILTERING ---
st.sidebar.header("🎛️ Priority Multipliers & Weights")
w_flood = st.sidebar.slider("Flood Mitigation Weight", 0.0, 1.0, 0.20, 0.05)
w_sustain = st.sidebar.slider("Sustainability Weight", 0.0, 1.0, 0.15, 0.05)
w_econ = st.sidebar.slider("Economic Impact Weight", 0.0, 1.0, 0.15, 0.05)
w_equity = st.sidebar.slider("Social Justice & Equity Weight", 0.0, 1.0, 0.20, 0.05)
w_risk = st.sidebar.slider("Risk Mitigation Weight", 0.0, 1.0, 0.20, 0.05)
w_construct = st.sidebar.slider("Constructability Weight", 0.0, 1.0, 0.10, 0.05)
total_weight = w_flood + w_sustain + w_econ + w_equity + w_risk + w_construct
if total_weight == 0:
   total_weight = 1.0
df['Custom_Composite_Score'] = (
   (df['Flood_Mitigation_Score'] * w_flood) +
   (df['Sustainability_Score'] * w_sustain) +
   (df['Economic_Impact_Score'] * w_econ) +
   (df['Social_Justice_Equity_Score'] * w_equity) +
   (df['Risk_Mitigation_Score'] * w_risk) +
   (df['Constructability_Score'] * w_construct)
) / total_weight
df['Custom_Composite_Score'] = df['Custom_Composite_Score'].round(2)
# Global Filters
st.sidebar.header("🔍 Global Dashboard Filters")
all_depts = sorted(df['Department'].unique().tolist()) if not df.empty else []
selected_depts = st.sidebar.multiselect("Filter by Department", all_depts, default=all_depts)
all_phases = sorted(df['Phase'].unique().tolist()) if not df.empty else []
selected_phases = st.sidebar.multiselect("Filter by Project Phase", all_phases, default=all_phases)
# Apply Filters
filtered_df = df[df['Department'].isin(selected_depts) & df['Phase'].isin(selected_phases)].copy()
filtered_df = filtered_df.sort_values(by='Custom_Composite_Score', ascending=False)
# --- 3. TOP-LEVEL KPI METRICS ---
total_investment = filtered_df['Capital_Cost'].sum() if not filtered_df.empty else 0
avg_priority_score = filtered_df['Custom_Composite_Score'].mean() if not filtered_df.empty else 0
kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Total Program Portfolio Value", f"${total_investment:,.0f}")
kpi2.metric("Filtered Projects Counter", f"{len(filtered_df)} Projects")
kpi3.metric("Average Portfolio Priority Score", f"{avg_priority_score:.2f} / 5.0")
st.markdown("---")
# --- 4. LEAFLET GEOSPATIAL MAP & PRIORITIZATION LEADERBOARD ---
col1, col2 = st.columns([3, 2])
with col1:
   st.subheader("📍 Interactive Geospatial Portfolio Map (Leaflet)")
   valid_coords = filtered_df.dropna(subset=['Latitude', 'Longitude'])
   if not valid_coords.empty:
       center_lat = valid_coords['Latitude'].median()
       center_lon = valid_coords['Longitude'].median()
   else:
       center_lat, center_lon = 28.5383, -81.3792
   m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="cartodbpositron")
   marker_cluster = MarkerCluster().add_to(m)
   for _, row in valid_coords.iterrows():
       score = row['Custom_Composite_Score']
       pin_color = 'red' if score >= 4.0 else 'orange' if score >= 3.0 else 'green'
       popup_html = f"""
<div style="font-family: Arial, sans-serif; width: 220px;">
<h5 style="margin:0 0 5px 0; color:#1f77b4;">{row['Project_Name']}</h5>
<b>ID:</b> {row['CIP_ID']}<br>
<b>Dept:</b> {row['Department']}<br>
<b>Phase:</b> {row['Phase']}<br>
<b>Capital Cost:</b> ${row['Capital_Cost']:,.0f}<br>
<hr style="margin:5px 0;">
<span style="background-color:{pin_color}; color:white; padding:2px 6px; border-radius:3px; font-weight:bold;">
               Priority Score: {score:.2f}
</span>
</div>
       """
       folium.CircleMarker(
           location=[row['Latitude'], row['Longitude']],
           radius=8,
           color=pin_color,
           fill=True,
           fill_color=pin_color,
           fill_opacity=0.7,
           popup=folium.Popup(popup_html, max_width=250)
       ).add_to(marker_cluster)
   st_folium(m, width="100%", height=450, key="map", returned_objects=[])
with col2:
   st.subheader("🏆 Dynamic Prioritization Leaderboard")
   st.dataframe(
       filtered_df[['CIP_ID', 'Project_Name', 'Department', 'Capital_Cost', 'Custom_Composite_Score']],
       use_container_width=True,
       height=450,
       column_config={
           "Capital_Cost": st.column_config.NumberColumn("Capital Cost", format="$%,.0f"),
           "Custom_Composite_Score": st.column_config.ProgressColumn(
               "Priority Rating", min_value=1.0, max_value=5.0, format="%.2f"
           )
       },
       hide_index=True
   )
st.markdown("---")
# --- 5. TEMPORAL FINANCIAL DISTRIBUTION LOGIC (Linear Cost Spreading) ---
st.subheader("⏳ Multi-Year Capital Cash Flow Projections (Linear Financial Distribution)")
cash_flow_records = []
if not filtered_df.empty:
   for _, row in filtered_df.iterrows():
       duration_days = (row['End_Dt'] - row['Start_Dt']).days
       if duration_days <= 0:
           duration_days = 1
       daily_rate = row['Capital_Cost'] / duration_days
       date_range = pd.date_range(start=row['Start_Dt'], end=row['End_Dt'], freq='D')
       for day in date_range:
           cash_flow_records.append({
               'Year': day.year,
               'Department': row['Department'],
               'Daily_Expenditure': daily_rate
           })
if len(cash_flow_records) > 0:
   cf_df = pd.DataFrame(cash_flow_records)
   # 5a. Annual Stacked Bar Aggregate
   annual_chart_data = cf_df.groupby(['Year', 'Department'])['Daily_Expenditure'].sum().reset_index()
   annual_chart_data.rename(columns={'Daily_Expenditure': 'Annual_Cost'}, inplace=True)
   annual_chart_data = annual_chart_data.sort_values(by='Year')
   # 5b. Cumulative Curve Aggregate
   cumulative_chart_data = cf_df.groupby('Year')['Daily_Expenditure'].sum().reset_index()
   cumulative_chart_data = cumulative_chart_data.sort_values(by='Year')
   cumulative_chart_data['Cumulative_Cost'] = cumulative_chart_data['Daily_Expenditure'].cumsum()
   col3, col4 = st.columns(2)
   with col3:
       fig_bar = px.bar(
           annual_chart_data,
           x='Year',
           y='Annual_Cost',
           color='Department',
           title="Annual Funding Allocations by Department",
           labels={'Annual_Cost': 'Allocated Budget ($)', 'Year': 'Calendar Year'},
           template='plotly_white'
       )
       fig_bar.update_layout(xaxis_type='category', barmode='stack', hovermode='x unified')
       st.plotly_chart(fig_bar, use_container_width=True)
   with col4:
       fig_line = go.Figure()
       fig_line.add_trace(go.Scatter(
           x=cumulative_chart_data['Year'],
           y=cumulative_chart_data['Cumulative_Cost'],
           mode='lines+markers',
           name='Cumulative Total Program Cost',
           line=dict(color='#2ca02c', width=4),
           marker=dict(size=8, symbol='diamond')
       ))
       fig_line.update_layout(
           title="Cumulative Capital Program Expenditure Profile",
           xaxis_title="Calendar Year",
           yaxis_title="Total Multi-Year Commitment ($)",
           xaxis=dict(type='category'),
           template='plotly_white',
           hovermode='x unified'
       )
       st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("Please adjust global dashboard filters or verify your project date columns to generate multi-year financial profiles.")
