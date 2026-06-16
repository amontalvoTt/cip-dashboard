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

# 1. EMULATE PRODUCTION THEME & STYLING VIA CUSTOM CSS INJECTION
st.set_page_config(layout="wide", page_title="CIP Optimization Platform")

st.markdown("""
    <style>
        /* Import industrial typography */
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&display=swap');
        
        /* Overhaul structural fonts */
        html, body, [class*="css"], .stMarkdown, p, span, label {
            font-family: 'DM+Mono', monospace !important;
            font-size: 0.92rem !important;
        }
        
        /* Standardize headers to engineering style */
        h1, h2, h3, h4, h5, h6 {
            font-family: 'DM+Mono', monospace !important;
            font-weight: 500 !important;
            letter-spacing: -0.03em !important;
            color: #1e293b !important;
            text-transform: uppercase;
        }
        
        /* Industrial Telemetry Cards (Matching index_v5 style containers) */
        div[data-testid="stMetricValue"] {
            font-family: 'DM+Mono', monospace !important;
            font-size: 1.75rem !important;
            font-weight: 500 !important;
            color: #0f172a !important;
            letter-spacing: -0.02em;
        }
        div[data-testid="stMetricLabel"] {
            text-transform: uppercase !important;
            font-size: 0.75rem !important;
            letter-spacing: 0.05em !important;
            color: #64748b !important;
        }
        div[data-testid="stMetric"] {
            background-color: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            padding: 15px !important;
            border-radius: 4px !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
        }
        
        /* Refine sidebar execution pane styling */
        section[data-testid="stSidebar"] {
            background-color: #f8fafc !important;
            border-right: 1px solid #e2e8f0 !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🎛️ CIP Optimization & Schedule Reanimation Platform")
st.markdown("---")

# --- 2. AUTOMATED DATA INGESTION ENGINE ---
@st.cache_data
def load_and_clean_data(file_source):
    if isinstance(file_source, (str, os.PathLike)):
        df = pd.read_csv(file_source, encoding='utf-8-sig', engine='python', on_bad_lines='skip')
    else:
        raw_bytes = file_source.read()
        raw_text = raw_bytes.decode('utf-8-sig', errors='ignore')
        df = pd.read_csv(io.StringIO(raw_text), engine='python', on_bad_lines='skip')
        
    for col in ['Capital_Cost', 'Operating_Cost_Annual']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('$', '', regex=False)
            df[col] = df[col].str.replace(',', '', regex=False)
            df[col] = df[col].str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    df['Start_Dt'] = pd.to_datetime(df['Project_Start_Date'], errors='coerce', format='mixed')
    df['End_Dt'] = pd.to_datetime(df['Project_End_Date'], errors='coerce', format='mixed')
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    
    score_cols = [
        'Flood_Mitigation_Score', 'Sustainability_Score', 'Economic_Impact_Score',
        'Social_Justice_Equity_Score', 'Risk_Mitigation_Score', 'Constructability_Score'
    ]
    for col in score_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(3)
            
    return df.dropna(subset=['Start_Dt', 'End_Dt'])

# Ingestion Routing Logic
uploaded_file = st.sidebar.file_uploader("📂 INGEST REVISED PORTFOLIO (CSV)", type=["csv"])
df = None
default_filename = "CIP_Table.csv"

if uploaded_file is not None:
    df = load_and_clean_data(uploaded_file)
elif os.path.exists(default_filename):
    df = load_and_clean_data(default_filename)

if df is None or df.empty:
    st.info("💡 Awaiting source dataset injection. Please drop standard CIP_Table.csv file into workspace to initialize framework.")
    st.stop()

# --- 3. DYNAMIC CRITERIA PRIORITIZATION INTERFACE ---
st.sidebar.markdown("### 🛠️ SCORING SYSTEM COEFFICIENTS")

w_flood = st.sidebar.slider("Flood Mitigation Matrix", 0.0, 1.0, 0.20, 0.05)
w_sustain = st.sidebar.slider("Sustainability Target", 0.0, 1.0, 0.15, 0.05)
w_econ = st.sidebar.slider("Economic ROI Profile", 0.0, 1.0, 0.15, 0.05)
w_equity = st.sidebar.slider("Social Justice / Equity", 0.0, 1.0, 0.20, 0.05)
w_risk = st.sidebar.slider("Asset Risk Mitigation", 0.0, 1.0, 0.20, 0.05)
w_construct = st.sidebar.slider("Constructability Index", 0.0, 1.0, 0.10, 0.05)

total_weight = w_flood + w_sustain + w_econ + w_equity + w_risk + w_construct
if total_weight == 0: total_weight = 1.0

df['Custom_Composite_Score'] = (
    (df['Flood_Mitigation_Score'] * w_flood) +
    (df['Sustainability_Score'] * w_sustain) +
    (df['Economic_Impact_Score'] * w_econ) +
    (df['Social_Justice_Equity_Score'] * w_equity) +
    (df['Risk_Mitigation_Score'] * w_risk) +
    (df['Constructability_Score'] * w_construct)
) / total_weight
df['Custom_Composite_Score'] = df['Custom_Composite_Score'].round(2)

# Operational Namespace Filters
st.sidebar.markdown("### 🔍 DOMAIN MATRIX FILTERS")
all_depts = sorted(df['Department'].unique().tolist())
selected_depts = st.sidebar.multiselect("OPERATING DEPARTMENT", all_depts, default=all_depts)

all_phases = sorted(df['Phase'].unique().tolist())
selected_phases = st.sidebar.multiselect("PROJECT LIFE CYCLE PHASE", all_phases, default=all_phases)

filtered_df = df[df['Department'].isin(selected_depts) & df['Phase'].isin(selected_phases)].copy()

# --- 4. SCENARIO REANIMATION ENGINE (SCHEDULE SHIFT SIMULATION) ---
st.sidebar.markdown("### ⏳ SCHEDULE REANIMATION SANDBOX")
st.sidebar.markdown("Test the visual or financial impact of delaying specific capital components:")

enable_reanimation = st.sidebar.checkbox("Activate Simulation Blueprint", value=False)
reanimated_project_id = None
time_shift_months = 0

if enable_reanimation and not filtered_df.empty:
    project_options = filtered_df['CIP_ID'].tolist()
    reanimated_project_id = st.sidebar.selectbox("SELECT SIMULATION TARGET", project_options)
    time_shift_months = st.sidebar.slider("SHIFT TARGET TIMELINE (MONTHS)", -36, 64, 12, step=6)

# Apply Reanimation shifts to operational vectors
filtered_df['Active_Start_Dt'] = filtered_df['Start_Dt']
filtered_df['Active_End_Dt'] = filtered_df['End_Dt']

if enable_reanimation and reanimated_project_id:
    shift_delta = pd.DateOffset(months=time_shift_months)
    idx_match = filtered_df['CIP_ID'] == reanimated_project_id
    filtered_df.loc[idx_match, 'Active_Start_Dt'] = filtered_df.loc[idx_match, 'Start_Dt'] + shift_delta
    filtered_df.loc[idx_match, 'Active_End_Dt'] = filtered_df.loc[idx_match, 'End_Dt'] + shift_delta

filtered_df = filtered_df.sort_values(by='Custom_Composite_Score', ascending=False)

# --- 5. SYSTEM TELEMETRY DISPLAY ---
total_investment = filtered_df['Capital_Cost'].sum() if not filtered_df.empty else 0
avg_priority_score = filtered_df['Custom_Composite_Score'].mean() if not filtered_df.empty else 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("PORTFOLIO COMMITMENT", f"${total_investment:,.0f}")
kpi2.metric("ACTIVE TELEMETRY NODES", f"{len(filtered_df)} Projects")
kpi3.metric("COMPOSITE PERFORMANCE AVERAGE", f"{avg_priority_score:.2f} / 5.0")

st.markdown("---")

# --- 6. SPATIAL INFRASTRUCTURE & SCORING LEADERBOARD VIEW ---
col1, col2 = st.columns([3, 2])

with col1:
    st.markdown("### 📍 GEOSPATIAL RUNTIME CONTAINER (LEAFLET)")
    valid_coords = filtered_df.dropna(subset=['Latitude', 'Longitude'])
    center_lat = valid_coords['Latitude'].median() if not valid_coords.empty else 28.5383
    center_lon = valid_coords['Longitude'].median() if not valid_coords.empty else -81.3792
        
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="cartodbpositron")
    marker_cluster = MarkerCluster().add_to(m)
    
    for _, row in valid_coords.iterrows():
        score = row['Custom_Composite_Score']
        # Hex palette mirroring document spec
        pin_color = '#c0392b' if score >= 4.0 else '#e8960e' if score >= 3.0 else '#0a8f72'
        
        is_simulated = " (SIMULATED SHIFT)" if enable_reanimation and row['CIP_ID'] == reanimated_project_id else ""
        
        popup_html = f"""
        <div style="font-family: 'DM Mono', monospace; font-size:11px; width: 240px; color:#334155;">
            <h6 style="margin:0 0 5px 0; text-transform:uppercase; color:#0f172a; font-weight:bold;">{row['Project_Name']}{is_simulated}</h6>
            <b>NODE IDENTIFIER:</b> {row['CIP_ID']}<br>
            <b>DEPT MATRIX:</b> {row['Department']}<br>
            <b>TIMELINE VECTORS:</b> {row['Active_Start_Dt'].strftime('%Y-%m')} to {row['Active_End_Dt'].strftime('%Y-%m')}<br>
            <b>CAPITAL VALUE:</b> ${row['Capital_Cost']:,.0f}<br>
            <div style="margin-top:8px; padding:3px; background:{pin_color}; color:white; text-align:center; font-weight:bold; border-radius:2px;">
                COMPOSITE EVALUATION: {score:.2f}
            </div>
        </div>
        """
        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=7,
            color=pin_color,
            fill=True,
            fill_color=pin_color,
            fill_opacity=0.75,
            popup=folium.Popup(popup_html, max_width=260)
        ).add_to(marker_cluster)
        
    st_folium(m, width="100%", height=460, key="gis_map", returned_objects=[])

with col2:
    st.markdown("### 🏆 REAL-TIME EVALUATION OPTIMIZATION MATRIX")
    st.dataframe(
        filtered_df[['CIP_ID', 'Project_Name', 'Department', 'Capital_Cost', 'Custom_Composite_Score']],
        use_container_width=True,
        height=460,
        column_config={
            "CIP_ID": "ID",
            "Project_Name": "PROJECT DESIGNATION",
            "Department": "DOMAIN",
            "Capital_Cost": st.column_config.NumberColumn("CAPITAL COST", format="$%,.0f"),
            "Custom_Composite_Score": st.column_config.NumberColumn("SCORE", format="%.2f")
        },
        hide_index=True
    )

st.markdown("---")

# --- 7. TEMPORAL DISTRIBUTION RENDERING ENGINE ---
st.markdown("### ⏳ MULTI-YEAR CAPITAL DISTRIBUTION CHRONICLER")

cash_flow_records = []
if not filtered_df.empty:
    for _, row in filtered_df.iterrows():
        duration_days = (row['Active_End_Dt'] - row['Active_Start_Dt']).days
        if duration_days <= 0: duration_days = 1
            
        daily_rate = row['Capital_Cost'] / duration_days
        date_range = pd.date_range(start=row['Active_Start_Dt'], end=row['Active_End_Dt'], freq='D')
        
        for day in date_range:
            cash_flow_records.append({
                'Year': day.year,
                'Department': row['Department'],
                'Daily_Expenditure': daily_rate
            })

if len(cash_flow_records) > 0:
    cf_df = pd.DataFrame(cash_flow_records)
    
    # 7a. Annual Bins Aggregate
    annual_chart_data = cf_df.groupby(['Year', 'Department'])['Daily_Expenditure'].sum().reset_index()
    annual_chart_data.rename(columns={'Daily_Expenditure': 'Annual_Cost'}, inplace=True)
    annual_chart_data = annual_chart_data.sort_values(by='Year')
    
    # 7b. Cumulative Line Engine
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
            labels={'Annual_Cost': 'FINANCIAL OUTFLOW ($)', 'Year': 'FISCAL CALENDAR YEAR'},
            template='plotly_white',
            color_discrete_sequence=px.colors.qualitative.Slate
        )
        fig_bar.update_layout(
            font_family="DM Mono",
            xaxis_type='category',
            barmode='stack',
            hovermode='x unified',
            title_text="ANNUALIZED CAPITAL EXPENDITURE OUTFLOW",
            title_font_size=14,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with col4:
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=cumulative_chart_data['Year'],
            y=cumulative_chart_data['Cumulative_Cost'],
            mode='lines+markers',
            name='CUMULATIVE COMMITMENT',
            line=dict(color='#0f172a', width=3),
            marker=dict(size=7, symbol='square', color='#64748b')
        ))
        fig_line.update_layout(
            font_family="DM Mono",
            title_text="CUMULATIVE PORTFOLIO INVESTMENTS PROFILE",
            title_font_size=14,
            xaxis_title="FISCAL CALENDAR YEAR",
            yaxis_title="TOTAL COMMITTED CAPITAL ($)",
            xaxis=dict(type='category'),
            template='plotly_white',
            hovermode='x unified'
        )
        st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("System configuration metrics yielded no active temporal sequences.")
