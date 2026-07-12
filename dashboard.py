# ========================================
# AfyaMetrix — Streamlit Dashboard
# File: afyametrix/utils/dashboard.py
# ========================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
import requests
import json
from datetime import datetime
import time
import os

# ========================================
# PAGE CONFIGURATION
# ========================================

st.set_page_config(
    page_title="AfyaMetrix — Pan-Africa Health Intelligence",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================================
# THEME & STYLING
# ========================================

st.markdown("""
<style>
    /* Main background */
    .stApp {
        background-color: #0D1117;
        color: #E8EDF3;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    
    /* Metric cards */
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, #161B22, #1C2128);
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 16px;
    }
    
    /* Headers */
    h1, h2, h3 { color: #E8EDF3 !important; }
    
    /* Alert boxes */
    .alert-critical {
        background: rgba(232, 64, 42, 0.15);
        border-left: 4px solid #E8402A;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0;
    }
    .alert-high {
        background: rgba(245, 166, 35, 0.15);
        border-left: 4px solid #F5A623;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0;
    }
    .alert-medium {
        background: rgba(255, 215, 0, 0.1);
        border-left: 4px solid #FFD700;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0;
    }
    
    /* Narrative box */
    .narrative-box {
        background: linear-gradient(135deg, #0A7B6E22, #0A7B6E11);
        border: 1px solid #0A7B6E66;
        border-radius: 12px;
        padding: 20px;
        font-size: 14px;
        line-height: 1.8;
        white-space: pre-wrap;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab"] {
        color: #8B949E;
    }
    .stTabs [aria-selected="true"] {
        color: #0A7B6E !important;
        border-bottom-color: #0A7B6E !important;
    }
    
    /* Buttons */
    .stButton > button {
        background: #0A7B6E;
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }
    .stButton > button:hover {
        background: #0d9e8e;
        border: none;
    }
    
    /* Selectbox */
    .stSelectbox > div > div {
        background: #161B22;
        border-color: #30363D;
        color: #E8EDF3;
    }
    
    /* Divider */
    hr { border-color: #30363D; }
</style>
""", unsafe_allow_html=True)

# ========================================
# DATA LOADING
# ========================================

DATA_PATH = r"C:\Users\hassa\afyametrix\data\processed"
API_BASE  = "http://127.0.0.1:8000"

@st.cache_data(ttl=300)  # cache for 5 minutes
def load_all_data():
    """Load all processed datasets."""
    data = {}
    files = {
        'regional_risk':  'regional_risk_summary.csv',
        'clusters':       'region_clusters.csv',
        'forecasts':      'forecast_summary.csv',
        'allocations':    'resource_allocations.csv',
        'cross_border':   'cross_border_alerts.csv',
        'quality':        'data_quality_scores.csv',
        'narratives':     'region_narratives.csv',
    }
    for key, filename in files.items():
        path = os.path.join(DATA_PATH, filename)
        try:
            df = pd.read_csv(path)
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            data[key] = df
        except:
            data[key] = pd.DataFrame()
    return data

def check_api():
    """Check if FastAPI server is running."""
    try:
        r = requests.get(f"{API_BASE}/", timeout=2)
        return r.status_code == 200
    except:
        return False

# Load data
DATA = load_all_data()

# Get latest snapshot
risk_df  = DATA['regional_risk']
latest   = risk_df['date'].max()
snapshot = risk_df[risk_df['date'] == latest].copy()

# Merge cluster info
if not DATA['clusters'].empty:
    snapshot = snapshot.merge(
        DATA['clusters'][[
            'country', 'region', 'cluster_label',
            'intervention_priority', 'resource_multiplier'
        ]],
        on=['country', 'region'], how='left'
    )

# ========================================
# SIDEBAR
# ========================================

with st.sidebar:
    # Logo and title
    st.markdown("""
    <div style="text-align:center; padding: 20px 0 10px 0;">
        <div style="font-size:48px;">🌍</div>
        <h2 style="color:#0A7B6E; margin:8px 0 4px 0;">AfyaMetrix</h2>
        <p style="color:#8B949E; font-size:12px; margin:0;">
            Pan-Africa Health Intelligence
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # API status
    api_live = check_api()
    status_color = "#2E7D52" if api_live else "#E8402A"
    status_text  = "API Connected" if api_live else "API Offline"
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:8px; 
                padding:8px 12px; background:#161B22; 
                border-radius:8px; margin-bottom:16px;">
        <div style="width:8px; height:8px; background:{status_color}; 
                    border-radius:50%;"></div>
        <span style="font-size:13px; color:{status_color};">
            {status_text}
        </span>
        <span style="font-size:11px; color:#8B949E; margin-left:auto;">
            {latest.strftime('%b %d, %Y')}
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    # Navigation
    st.markdown("**NAVIGATION**")
    page = st.radio(
        label="",
        options=[
            "🏠 Command Center",
            "🗺️  Risk Map",
            "📈 Disease Trends",
            "🚨 Active Alerts",
            "📦 Resource Allocation",
            "🌍 Cross-Border",
            "🧠 AI Narratives",
            "🎤 Voice Assistant",
            "📊 Data Quality",
        ],
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # Filters
    st.markdown("**FILTERS**")
    
    all_countries = sorted(snapshot['country'].unique().tolist())
    selected_countries = st.multiselect(
        "Countries",
        options=all_countries,
        default=all_countries,
        label_visibility="collapsed"
    )
    
    risk_threshold = st.slider(
        "Min Risk Score", 0, 100, 0
    )
    
    # Language selector
    st.divider()
    st.markdown("**LANGUAGE / LUGHA / LANGUE**")
    language = st.selectbox(
        "",
        options=["🇬🇧 English", "🇫🇷 Français", 
                 "🇰🇪 Kiswahili", "🇳🇬 Hausa", "🇪🇹 Amharic"],
        label_visibility="collapsed"
    )
    lang_code = {"🇬🇧 English": "en", "🇫🇷 Français": "fr",
                 "🇰🇪 Kiswahili": "sw", "🇳🇬 Hausa": "ha",
                 "🇪🇹 Amharic": "am"}[language]
    
    # Dark/Light mode note
    st.divider()
    st.markdown("""
    <p style="font-size:11px; color:#8B949E; text-align:center;">
        AfyaMetrix v1.0 · Round 1<br>
        Africa Agility Hackathon 2026
    </p>
    """, unsafe_allow_html=True)

# Apply filters
filtered = snapshot[
    snapshot['country'].isin(selected_countries) &
    (snapshot['risk_score'] >= risk_threshold)
].copy()

# ========================================
# PAGE: COMMAND CENTER
# ========================================

if page == "🏠 Command Center":
    
    st.markdown("## 🌍 AfyaMetrix Command Center")
    st.markdown(
        f"*Real-time health intelligence for Africa · "
        f"Data as of {latest.strftime('%B %d, %Y')}*"
    )
    
    st.divider()
    
    # --- KPI METRICS ROW ---
    col1, col2, col3, col4, col5 = st.columns(5)
    
    critical = filtered[filtered['risk_score'] >= 75]
    high     = filtered[
        (filtered['risk_score'] >= 55) & 
        (filtered['risk_score'] < 75)
    ]
    cross_alerts = DATA['cross_border']
    
    with col1:
        st.metric(
            "🔴 Critical Regions",
            len(critical),
            delta=None,
            help="Regions with risk score ≥ 75"
        )
    with col2:
        st.metric(
            "🟠 High Risk",
            len(high),
            help="Risk score 55-75"
        )
    with col3:
        st.metric(
            "🌍 Cross-Border Alerts",
            len(cross_alerts),
            help="Active spread alerts"
        )
    with col4:
        st.metric(
            "📊 Avg Risk Score",
            f"{filtered['risk_score'].mean():.1f}",
            help="Average across all regions"
        )
    with col5:
        st.metric(
            "🏥 Total Cases Today",
            f"{filtered['total_cases'].sum():,.0f}",
            help="Aggregate case count"
        )
    
    st.divider()
    
    col_left, col_right = st.columns([1.6, 1])
    
    with col_left:
        # --- RISK SCORE BAR CHART ---
        st.markdown("#### 📊 Risk Scores by Region")
        
        top_regions = filtered.nlargest(20, 'risk_score')
        
        colors = top_regions['risk_score'].apply(
            lambda x: '#E8402A' if x >= 75 else
                      '#F5A623' if x >= 55 else
                      '#FFD700' if x >= 30 else '#2E7D52'
        )
        
        fig = go.Figure(go.Bar(
            x=top_regions['risk_score'],
            y=top_regions['region'] + ', ' + top_regions['country'],
            orientation='h',
            marker_color=colors,
            text=top_regions['risk_score'].round(1),
            textposition='outside',
            hovertemplate=(
                '<b>%{y}</b><br>'
                'Risk Score: %{x:.1f}<br>'
                'Disease: ' + top_regions['top_disease'].fillna('Unknown') +
                '<extra></extra>'
            )
        ))
        
        fig.update_layout(
            height=500,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#E8EDF3',
            xaxis=dict(
                gridcolor='#30363D',
                range=[0, 100]
            ),
            yaxis=dict(gridcolor='#30363D'),
            margin=dict(l=0, r=60, t=20, b=20),
            showlegend=False
        )
        
        # Add threshold lines
        fig.add_vline(
            x=75, line_dash="dash", 
            line_color="#E8402A", opacity=0.5,
            annotation_text="Critical"
        )
        fig.add_vline(
            x=55, line_dash="dash",
            line_color="#F5A623", opacity=0.5,
            annotation_text="High"
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col_right:
        # --- ACTIVE ALERTS PANEL ---
        st.markdown("#### 🚨 Active Alerts")
        
        alerts = filtered[
            (filtered['risk_score'] >= 50) |
            (filtered['active_alerts'] > 0)
        ].nlargest(8, 'risk_score')
        
        for _, row in alerts.iterrows():
            risk = row['risk_score']
            if risk >= 75:
                css_class = "alert-critical"
                icon = "🔴"
            elif risk >= 55:
                css_class = "alert-high"
                icon = "🟠"
            else:
                css_class = "alert-medium"
                icon = "🟡"
            
            disease = row.get('top_disease', 'Unknown')
            
            st.markdown(f"""
            <div class="{css_class}">
                <div style="font-weight:600; font-size:14px;">
                    {icon} {row['region']}, {row['country']}
                </div>
                <div style="font-size:12px; opacity:0.8; margin-top:4px;">
                    {disease} · Score: {risk:.0f}/100
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        
        # Cluster distribution pie
        st.markdown("#### 🧩 Cluster Distribution")
        if not DATA['clusters'].empty:
            cluster_counts = DATA['clusters']['cluster_label'].value_counts()
            fig_pie = px.pie(
                values=cluster_counts.values,
                names=cluster_counts.index,
                color_discrete_map={
                    '🔴 Critical Hotspots':   '#E8402A',
                    '🟠 High Burden Zones':   '#F5A623',
                    '🟡 Emerging Risk Areas': '#FFD700',
                    '🟢 Stable Regions':      '#2E7D52',
                },
                hole=0.4
            )
            fig_pie.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                font_color='#E8EDF3',
                margin=dict(l=0, r=0, t=0, b=0),
                height=200,
                showlegend=True,
                legend=dict(font=dict(size=10))
            )
            st.plotly_chart(fig_pie, use_container_width=True)

# ========================================
# PAGE: RISK MAP
# ========================================

elif page == "🗺️  Risk Map":

    st.markdown("## 🗺️ Africa Risk Intelligence Map")
    st.markdown(
        "*Choropleth heatmap showing disease risk scores "
        "across all monitored countries*"
    )

    # ----------------------------------------
    # COUNTRY ISO CODES
    # ----------------------------------------
    COUNTRY_ISO = {
        'Kenya': 'KEN', 'Nigeria': 'NGA', 'Ethiopia': 'ETH',
        'Uganda': 'UGA', 'Tanzania': 'TZA', 'Ghana': 'GHA',
        'Senegal': 'SEN', 'DRC': 'COD', 'Zambia': 'ZMB', 'Sudan': 'SDN'
    }

    # Aggregate risk scores per country
    country_risk = filtered.groupby('country').agg(
        avg_risk    = ('risk_score', 'mean'),
        max_risk    = ('risk_score', 'max'),
        total_cases = ('total_cases', 'sum'),
        top_disease = ('top_disease', lambda x: x.value_counts().index[0]
                       if len(x) > 0 else 'Unknown')
    ).reset_index()

    country_risk['iso_alpha'] = country_risk['country'].map(COUNTRY_ISO)
    country_risk = country_risk.dropna(subset=['iso_alpha'])

    # ----------------------------------------
    # CONTROLS
    # ----------------------------------------
    col1, col2 = st.columns([3, 1])

    with col2:
        st.markdown("#### Map Controls")
        color_metric = st.radio(
            "Color by:",
            ["Average Risk", "Maximum Risk", "Total Cases"],
            index=0
        )
        metric_col = {
            "Average Risk":  "avg_risk",
            "Maximum Risk":  "max_risk",
            "Total Cases":   "total_cases"
        }[color_metric]

        st.divider()
        st.markdown("**Risk Scale:**")
        st.markdown("""
        🟢 Low (0–30)  
        🟡 Medium (31–55)  
        🟠 High (56–75)  
        🔴 Critical (76–100)
        """)

        st.divider()
        st.markdown("**Country Summary:**")
        for _, row in country_risk.sort_values(
            'avg_risk', ascending=False
        ).iterrows():
            risk = row['avg_risk']
            icon = ('🔴' if risk >= 75 else '🟠' if risk >= 55
                    else '🟡' if risk >= 30 else '🟢')
            st.markdown(
                f"{icon} **{row['country']}** — {risk:.0f}/100"
            )

    with col1:
        # ----------------------------------------
        # CHOROPLETH MAP
        # ----------------------------------------
        fig_map = px.choropleth(
            country_risk,
            locations='iso_alpha',
            color=metric_col,
            hover_name='country',
            hover_data={
                'avg_risk':    ':.1f',
                'max_risk':    ':.1f',
                'total_cases': ':,',
                'top_disease': True,
                'iso_alpha':   False
            },
            color_continuous_scale=[
                [0.0,  '#2E7D52'],
                [0.3,  '#FFD700'],
                [0.55, '#F5A623'],
                [1.0,  '#E8402A']
            ],
            range_color=[0, 100] if 'risk' in metric_col else None,
            scope='africa',
            title=f'AfyaMetrix — {color_metric} by Country',
            labels={
                'avg_risk':    'Avg Risk Score',
                'max_risk':    'Max Risk Score',
                'total_cases': 'Total Cases'
            }
        )

        fig_map.update_layout(
            paper_bgcolor='#0D1117',
            font_color='#E8EDF3',
            geo=dict(
                bgcolor='#0D1117',
                lakecolor='#0D1117',
                landcolor='#1C2128',
                showframe=True,
                framecolor='#30363D',
                showcoastlines=True,
                coastlinecolor='#30363D',
                showcountries=True,
                countrycolor='#30363D',
                showocean=True,
                oceancolor='#0D1117',
                projection_type='natural earth'
            ),
            coloraxis_colorbar=dict(
                title=color_metric,
                bgcolor='#161B22',
                bordercolor='#30363D',
                tickfont=dict(color='#E8EDF3'),
            ),
            margin=dict(l=0, r=0, t=40, b=0),
            height=520
        )

        st.plotly_chart(fig_map, use_container_width=True)

        # ----------------------------------------
        # REGION-LEVEL DETAIL TABLE
        # ----------------------------------------
        st.markdown("#### 📊 Region Detail")
        st.markdown(
            "*Click a country above then filter regions below*"
        )

        selected_country_map = st.selectbox(
            "Drill into country:",
            options=sorted(country_risk['country'].tolist()),
            key="map_country_drill"
        )

        region_detail = filtered[
            filtered['country'] == selected_country_map
        ].sort_values('risk_score', ascending=False)[[
            'region', 'risk_score', 'total_cases',
            'active_alerts', 'top_disease'
        ]].reset_index(drop=True)

        region_detail.columns = [
            'Region', 'Risk Score', 'Total Cases',
            'Active Alerts', 'Top Disease'
        ]

        st.dataframe(
            region_detail,
            use_container_width=True,
            hide_index=True
        )

# ========================================
# PAGE: DISEASE TRENDS
# ========================================

elif page == "📈 Disease Trends":
    
    st.markdown("## 📈 Disease Trends & Forecasts")
    
    col1, col2 = st.columns(2)
    with col1:
        selected_country = st.selectbox(
            "Select Country", 
            options=all_countries
        )
    with col2:
        disease_list = sorted(risk_df['top_disease'].dropna().unique())
        selected_disease = st.selectbox(
            "Select Disease",
            options=["All"] + disease_list
        )
    
    # Time series chart
    country_data = risk_df[
        risk_df['country'] == selected_country
    ].copy()
    
    if selected_disease != "All":
        country_data = country_data[
            country_data['top_disease'] == selected_disease
        ]
    
    # Aggregate by date
    daily_agg = country_data.groupby('date').agg(
        total_cases   = ('total_cases', 'sum'),
        avg_risk      = ('risk_score', 'mean'),
        active_alerts = ('active_alerts', 'sum')
    ).reset_index()
    
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=[
            f'Total Cases Over Time — {selected_country}',
            'Average Risk Score'
        ],
        row_heights=[0.65, 0.35],
        shared_xaxes=True
    )
    
    fig.add_trace(go.Scatter(
        x=daily_agg['date'],
        y=daily_agg['total_cases'],
        mode='lines',
        name='Total Cases',
        line=dict(color='#0A7B6E', width=1.5),
        fill='tozeroy',
        fillcolor='rgba(10, 123, 110, 0.1)'
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=daily_agg['date'],
        y=daily_agg['avg_risk'],
        mode='lines',
        name='Risk Score',
        line=dict(color='#F5A623', width=2)
    ), row=2, col=1)
    
    fig.add_hline(
        y=55, line_dash="dash",
        line_color="#E8402A", opacity=0.5,
        row=2, col=1
    )
    
    fig.update_layout(
        height=500,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#E8EDF3',
        xaxis2=dict(gridcolor='#30363D'),
        yaxis=dict(gridcolor='#30363D'),
        yaxis2=dict(gridcolor='#30363D', range=[0, 100]),
        margin=dict(l=0, r=0, t=40, b=0)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Forecast table
    st.markdown("#### 🔮 30-Day Forecasts")
    
    if not DATA['forecasts'].empty:
        fc = DATA['forecasts'].copy()
        if selected_country in fc['country'].values:
            fc_filtered = fc[fc['country'] == selected_country]
        else:
            fc_filtered = fc
        
        fc_display = fc_filtered[[
            'country', 'region', 'disease',
            'forecast_avg_daily_cases', 'trend_direction',
            'model_confidence_pct', 'prophet_beats_baseline'
        ]].copy()
        
        fc_display.columns = [
            'Country', 'Region', 'Disease',
            'Avg Daily Cases (30d)', 'Trend',
            'Confidence %', 'Better Than Baseline'
        ]
        
        st.dataframe(
            fc_display,
            use_container_width=True,
            hide_index=True
        )

# ========================================
# PAGE: ACTIVE ALERTS
# ========================================

elif page == "🚨 Active Alerts":
    
    st.markdown("## 🚨 Active Outbreak Alerts")
    
    all_alerts = filtered[
        (filtered['risk_score'] >= 30) |
        (filtered['active_alerts'] > 0)
    ].sort_values('risk_score', ascending=False)
    
    # Summary counts
    c1, c2, c3 = st.columns(3)
    with c1:
        n = len(all_alerts[all_alerts['risk_score'] >= 75])
        st.metric("🔴 Critical", n)
    with c2:
        n = len(all_alerts[
            (all_alerts['risk_score'] >= 55) & 
            (all_alerts['risk_score'] < 75)
        ])
        st.metric("🟠 High", n)
    with c3:
        n = len(all_alerts[
            (all_alerts['risk_score'] >= 30) & 
            (all_alerts['risk_score'] < 55)
        ])
        st.metric("🟡 Medium", n)
    
    st.divider()
    
    for _, row in all_alerts.iterrows():
        risk    = row['risk_score']
        disease = row.get('top_disease', 'Unknown')
        
        if risk >= 75:
            icon  = "🔴"
            level = "CRITICAL"
        elif risk >= 55:
            icon  = "🟠"
            level = "HIGH"
        else:
            icon  = "🟡"
            level = "MEDIUM"
        
        with st.expander(
            f"{icon} {level} — {row['region']}, {row['country']} "
            f"| Risk: {risk:.0f}/100 | {disease}"
        ):
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Risk Score", f"{risk:.1f}/100")
            with col_b:
                st.metric("Total Cases", f"{int(row.get('total_cases', 0)):,}")
            with col_c:
                st.metric("Active Alerts", int(row.get('active_alerts', 0)))
            
            cluster = row.get('cluster_label', 'Unknown')
            priority = row.get('intervention_priority', 'ROUTINE')
            st.markdown(f"**Cluster:** {cluster}  |  **Priority:** {priority}")

# ========================================
# PAGE: RESOURCE ALLOCATION
# ========================================

elif page == "📦 Resource Allocation":
    
    st.markdown("## 📦 Resource Allocation Engine")
    st.markdown(
        "*AI-driven distribution of health resources "
        "based on risk scores and population need*"
    )
    
    if DATA['allocations'].empty:
        st.error("Allocation data not available")
    else:
        alloc = DATA['allocations'].copy()
        
        if selected_countries:
            alloc = alloc[alloc['country'].isin(selected_countries)]
        
        # Summary
        st.markdown("#### 📊 Monthly Resource Summary")
        
        resource_cols = [
            'vaccines', 'medicine_kits', 'test_kits',
            'ambulances', 'medical_personnel', 'budget_usd'
        ]
        
        available_cols = [
            c for c in resource_cols if c in alloc.columns
        ]
        
        if available_cols:
            cols = st.columns(len(available_cols))
            totals = {
                'vaccines': 50000, 'medicine_kits': 8000,
                'test_kits': 15000, 'ambulances': 50,
                'medical_personnel': 200, 'budget_usd': 2000000
            }
            icons = {
                'vaccines': '💉', 'medicine_kits': '🧰',
                'test_kits': '🧪', 'ambulances': '🚑',
                'medical_personnel': '👨‍⚕️', 'budget_usd': '💰'
            }
            for i, col_name in enumerate(available_cols):
                with cols[i]:
                    allocated = alloc[col_name].sum()
                    total     = totals.get(col_name, 1)
                    icon      = icons.get(col_name, '📦')
                    label     = col_name.replace('_', ' ').title()
                    st.metric(
                        f"{icon} {label}",
                        f"{int(allocated):,}",
                        delta=f"of {total:,} total"
                    )
        
        st.divider()
        
        # Top allocations table
        st.markdown("#### 🏥 Top 15 Region Allocations")
        
        display_cols = (
            ['country', 'region', 'risk_score', 'cluster_label'] +
            available_cols
        )
        
        display_alloc = alloc.sort_values(
            'risk_score', ascending=False
        ).head(15)[display_cols]
        
        st.dataframe(
            display_alloc,
            use_container_width=True,
            hide_index=True
        )
        
        # Vaccine distribution bar chart
        if 'vaccines' in alloc.columns:
            st.markdown("#### 💉 Vaccine Distribution by Country")
            
            vax_by_country = alloc.groupby('country')['vaccines'].sum()\
                .reset_index().sort_values('vaccines', ascending=True)
            
            fig = px.bar(
                vax_by_country,
                x='vaccines',
                y='country',
                orientation='h',
                color='vaccines',
                color_continuous_scale=['#2E7D52', '#F5A623', '#E8402A'],
                template='plotly_dark'
            )
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=350,
                margin=dict(l=0, r=0, t=20, b=0),
                coloraxis_showscale=False
            )
            st.plotly_chart(fig, use_container_width=True)

# ========================================
# PAGE: CROSS-BORDER
# ========================================

elif page == "🌍 Cross-Border":
    
    st.markdown("## 🌍 Cross-Border Alert System")
    st.markdown(
        "*When disease spikes near a border, neighboring "
        "countries receive advance warning*"
    )
    
    cross = DATA['cross_border'].copy()
    
    if cross.empty:
        st.info("No cross-border alerts at current threshold")
    else:
        st.metric("Total Active Cross-Border Alerts", len(cross))
        st.divider()
        
        for _, row in cross.iterrows():
            severity = row.get('severity', '🟡 MODERATE')
            
            st.markdown(f"""
            <div class="alert-high" style="margin-bottom:12px;">
                <div style="font-size:16px; font-weight:700;">
                    {severity}
                </div>
                <div style="margin-top:8px; font-size:14px;">
                    <b>{row['source_region']}, {row['source_country']}</b>
                    → alerting <b>{row['target_country']}</b>
                </div>
                <div style="margin-top:6px; font-size:13px; opacity:0.85;">
                    Disease: {row['disease']} · 
                    Source Risk: {row['source_risk_score']:.0f}/100 · 
                    Spread Probability: {row['spread_probability']:.0f}%
                </div>
                <div style="margin-top:6px; font-size:12px; 
                            opacity:0.7; font-style:italic;">
                    → {row['recommended_action']}
                </div>
            </div>
            """, unsafe_allow_html=True)

# ========================================
# PAGE: AI NARRATIVES
# ========================================

elif page == "🧠 AI Narratives":
    
    st.markdown("## 🧠 AI Health Intelligence Briefs")
    st.markdown(
        "*Plain-language summaries that turn data into decisions*"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        nar_country = st.selectbox(
            "Select Country",
            options=all_countries,
            key="nar_country"
        )
    with col2:
        country_regions = sorted(
            snapshot[snapshot['country'] == nar_country]['region'].unique()
        )
        nar_region = st.selectbox(
            "Select Region",
            options=country_regions,
            key="nar_region"
        )
    
    if st.button("📝 Generate Intelligence Brief"):
        
        # Try pre-generated first
        narratives = DATA['narratives']
        match = narratives[
            (narratives['country'] == nar_country) &
            (narratives['region'] == nar_region)
        ] if not narratives.empty else pd.DataFrame()
        
        if len(match) > 0:
            row      = match.iloc[0]
            lang_col = f'narrative_{lang_code}'
            
            if lang_col not in row.index:
                lang_col = 'narrative_en'
            
            narrative_text = row.get(lang_col, row.get('narrative_en', ''))
            
            st.markdown(
                f'<div class="narrative-box">{narrative_text}</div>',
                unsafe_allow_html=True
            )
        else:
            # Generate from API
            try:
                r = requests.get(
                    f"{API_BASE}/api/narrative",
                    params={
                        "country":  nar_country,
                        "region":   nar_region,
                        "language": lang_code
                    },
                    timeout=5
                )
                if r.status_code == 200:
                    text = r.json().get('narrative', 'No narrative available')
                    st.markdown(
                        f'<div class="narrative-box">{text}</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.error("Could not generate narrative")
            except:
                # Fallback: generate from local data
                region_data = snapshot[
                    (snapshot['country'] == nar_country) &
                    (snapshot['region'] == nar_region)
                ]
                if len(region_data) > 0:
                    row  = region_data.iloc[0]
                    risk = row['risk_score']
                    st.markdown(f"""
                    <div class="narrative-box">
📍 HEALTH INTELLIGENCE BRIEF — {nar_region.upper()}, {nar_country.upper()}
{'═' * 50}
Generated: {datetime.now().strftime('%B %d, %Y')} | Risk Score: {risk:.0f}/100

SITUATION
{nar_region} currently has a risk score of {risk:.0f}/100.
Primary disease of concern: {row.get('top_disease', 'Unknown')}.
Total reported cases: {int(row.get('total_cases', 0)):,}.
Active outbreak alerts: {int(row.get('active_alerts', 0))}.

RECOMMENDED ACTION
{'Immediate response required.' if risk >= 75 else
 'Increased surveillance advised.' if risk >= 55 else
 'Continue routine monitoring.'}
                    </div>
                    """, unsafe_allow_html=True)

# ========================================
# PAGE: VOICE ASSISTANT
# ========================================

elif page == "🎤 Voice Assistant":

    st.markdown("## 🎤 Voice Assistant")
    st.markdown(
        "*Speak or type your query. "
        "The assistant will respond in text and voice.*"
    )

    # ----------------------------------------
    # BROWSER VOICE INTERFACE
    # ----------------------------------------
    # This uses the browser's Web Speech API for:
    # - Speech recognition (microphone input)
    # - Speech synthesis (text-to-speech output)
    # No external API needed — works fully in Chrome/Edge

    voice_html = """
    <div id="afya-voice" style="
        background: linear-gradient(135deg, #0A2A27, #0d1f1d);
        border: 1px solid #0A7B6E44;
        border-radius: 16px;
        padding: 28px;
        max-width: 680px;
        margin: 0 auto;
        font-family: 'Inter', sans-serif;
    ">
        <!-- Header -->
        <div style="display:flex; align-items:center; 
                    margin-bottom:24px; gap:12px;">
            <div style="
                width:52px; height:52px;
                background:linear-gradient(135deg, #0A7B6E, #0d9e8e);
                border-radius:50%;
                display:flex; align-items:center;
                justify-content:center;
                font-size:26px;
                box-shadow: 0 4px 16px rgba(10,123,110,0.4);
            ">🌍</div>
            <div>
                <div style="color:#E8EDF3; font-size:18px; font-weight:700;">
                    AfyaMetrix Voice Assistant
                </div>
                <div style="color:#0A7B6E; font-size:13px;">
                    Pan-Africa Health Intelligence
                </div>
            </div>
            <div style="margin-left:auto; display:flex; 
                        align-items:center; gap:6px;">
                <div id="status-dot" style="
                    width:10px; height:10px;
                    background:#2E7D52;
                    border-radius:50%;
                    box-shadow: 0 0 8px #2E7D52;
                "></div>
                <span id="status-text" style="
                    color:#2E7D52; font-size:12px;">Ready</span>
            </div>
        </div>

        <!-- Response display area -->
        <div id="response-area" style="
            background:rgba(255,255,255,0.04);
            border:1px solid #30363D;
            border-radius:12px;
            padding:18px;
            min-height:100px;
            margin-bottom:16px;
            color:#E8EDF3;
            font-size:15px;
            line-height:1.7;
        ">
            <span style="color:#8B949E;">
                👋 Welcome to AfyaMetrix.<br>
                Click the microphone button and speak,
                or use the quick command buttons below.
            </span>
        </div>

        <!-- What you said -->
        <div id="transcript-area" style="
            background:rgba(10,123,110,0.08);
            border:1px solid #0A7B6E33;
            border-radius:8px;
            padding:10px 14px;
            margin-bottom:20px;
            color:#8B949E;
            font-size:13px;
            min-height:38px;
            display:flex;
            align-items:center;
        ">
            <span id="transcript-text">
                Your words will appear here...
            </span>
        </div>

        <!-- Main mic button + controls -->
        <div style="display:flex; gap:12px; margin-bottom:20px;">

            <!-- Microphone button -->
            <button id="mic-btn"
                onmousedown="startListening()"
                onmouseup="stopListening()"
                ontouchstart="startListening()"
                ontouchend="stopListening()"
                style="
                    flex:1;
                    background:linear-gradient(135deg, #F5A623, #e0941a);
                    color:white;
                    border:none;
                    border-radius:12px;
                    padding:16px;
                    font-size:17px;
                    font-weight:700;
                    cursor:pointer;
                    box-shadow: 0 4px 16px rgba(245,166,35,0.3);
                    transition: all 0.15s;
                    letter-spacing:0.3px;
                ">
                🎤 Hold to Speak
            </button>

            <!-- Replay last response -->
            <button onclick="replayLastResponse()" style="
                background:rgba(10,123,110,0.2);
                color:#0A7B6E;
                border:1px solid #0A7B6E44;
                border-radius:12px;
                padding:16px 20px;
                font-size:20px;
                cursor:pointer;
                transition: all 0.15s;
            " title="Replay last response">🔊</button>

            <!-- Clear -->
            <button onclick="clearAll()" style="
                background:rgba(255,255,255,0.05);
                color:#8B949E;
                border:1px solid #30363D;
                border-radius:12px;
                padding:16px 20px;
                font-size:20px;
                cursor:pointer;
            " title="Clear">🗑️</button>

        </div>

        <!-- OR divider -->
        <div style="display:flex; align-items:center; 
                    gap:12px; margin-bottom:16px;">
            <div style="flex:1; height:1px; background:#30363D;"></div>
            <span style="color:#8B949E; font-size:12px;">
                OR TYPE YOUR QUERY
            </span>
            <div style="flex:1; height:1px; background:#30363D;"></div>
        </div>

        <!-- Text input -->
        <div style="display:flex; gap:10px; margin-bottom:20px;">
            <input id="text-input"
                type="text"
                placeholder="e.g. show high risk regions..."
                onkeydown="if(event.key==='Enter') sendTextQuery()"
                style="
                    flex:1;
                    background:rgba(255,255,255,0.06);
                    border:1px solid #30363D;
                    border-radius:10px;
                    padding:12px 16px;
                    color:#E8EDF3;
                    font-size:14px;
                    outline:none;
                "/>
            <button onclick="sendTextQuery()" style="
                background:#0A7B6E;
                color:white;
                border:none;
                border-radius:10px;
                padding:12px 20px;
                font-size:14px;
                font-weight:600;
                cursor:pointer;
            ">Ask →</button>
        </div>

        <!-- Quick command buttons -->
        <div>
            <div style="color:#8B949E; font-size:11px; 
                        letter-spacing:1px; margin-bottom:10px;">
                QUICK COMMANDS
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:8px;">
                <button onclick="quickQuery('show high risk regions')"
                    style="background:rgba(232,64,42,0.15);
                           color:#E8402A;
                           border:1px solid rgba(232,64,42,0.3);
                           border-radius:8px; padding:8px 14px;
                           font-size:13px; cursor:pointer;">
                    🔴 High Risk Regions
                </button>
                <button onclick="quickQuery('give me a full overview')"
                    style="background:rgba(10,123,110,0.15);
                           color:#0A7B6E;
                           border:1px solid rgba(10,123,110,0.3);
                           border-radius:8px; padding:8px 14px;
                           font-size:13px; cursor:pointer;">
                    📊 Full Overview
                </button>
                <button onclick="quickQuery('cross border alerts')"
                    style="background:rgba(74,144,217,0.15);
                           color:#4A90D9;
                           border:1px solid rgba(74,144,217,0.3);
                           border-radius:8px; padding:8px 14px;
                           font-size:13px; cursor:pointer;">
                    🌍 Border Alerts
                </button>
                <button onclick="quickQuery('malaria status')"
                    style="background:rgba(245,166,35,0.15);
                           color:#F5A623;
                           border:1px solid rgba(245,166,35,0.3);
                           border-radius:8px; padding:8px 14px;
                           font-size:13px; cursor:pointer;">
                    🦟 Malaria
                </button>
                <button onclick="quickQuery('cholera outbreak')"
                    style="background:rgba(155,89,182,0.15);
                           color:#9B59B6;
                           border:1px solid rgba(155,89,182,0.3);
                           border-radius:8px; padding:8px 14px;
                           font-size:13px; cursor:pointer;">
                    💧 Cholera
                </button>
                <button onclick="quickQuery('Ethiopia health update')"
                    style="background:rgba(46,125,82,0.15);
                           color:#2E7D52;
                           border:1px solid rgba(46,125,82,0.3);
                           border-radius:8px; padding:8px 14px;
                           font-size:13px; cursor:pointer;">
                    🇪🇹 Ethiopia
                </button>
                <button onclick="quickQuery('Nigeria status')"
                    style="background:rgba(232,64,42,0.1);
                           color:#E8402A;
                           border:1px solid rgba(232,64,42,0.2);
                           border-radius:8px; padding:8px 14px;
                           font-size:13px; cursor:pointer;">
                    🇳🇬 Nigeria
                </button>
                <button onclick="quickQuery('DRC critical alert')"
                    style="background:rgba(245,166,35,0.1);
                           color:#F5A623;
                           border:1px solid rgba(245,166,35,0.2);
                           border-radius:8px; padding:8px 14px;
                           font-size:13px; cursor:pointer;">
                    🇨🇩 DRC
                </button>
            </div>
        </div>

        <!-- Language selector for TTS -->
        <div style="margin-top:20px; padding-top:16px; 
                    border-top:1px solid #30363D;">
            <div style="color:#8B949E; font-size:11px; 
                        letter-spacing:1px; margin-bottom:8px;">
                VOICE OUTPUT LANGUAGE
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
                <button onclick="setLang('en-US')" id="lang-en"
                    class="lang-btn active-lang"
                    style="background:#0A7B6E22; color:#0A7B6E;
                           border:1px solid #0A7B6E55; border-radius:6px;
                           padding:6px 12px; font-size:12px; cursor:pointer;">
                    🇬🇧 English
                </button>
                <button onclick="setLang('fr-FR')" id="lang-fr"
                    class="lang-btn"
                    style="background:transparent; color:#8B949E;
                           border:1px solid #30363D; border-radius:6px;
                           padding:6px 12px; font-size:12px; cursor:pointer;">
                    🇫🇷 Français
                </button>
                <button onclick="setLang('sw')" id="lang-sw"
                    class="lang-btn"
                    style="background:transparent; color:#8B949E;
                           border:1px solid #30363D; border-radius:6px;
                           padding:6px 12px; font-size:12px; cursor:pointer;">
                    🇰🇪 Kiswahili
                </button>
            </div>
        </div>

    </div>

    <script>
    // ============================================
    // CONFIGURATION
    // ============================================
    const API_BASE    = 'http://127.0.0.1:8000';
    let currentLang   = 'en-US';
    let lastResponse  = '';
    let recognition   = null;
    let isListening   = false;
    let synth         = window.speechSynthesis;

    // ============================================
    // TEXT TO SPEECH
    // ============================================
    function speak(text, lang) {
        if (!synth) return;

        // Cancel any ongoing speech first
        synth.cancel();

        // Clean text for speech
        // Remove emojis and special chars that sound bad
        const cleanText = text
            .replace(/[🌍🔴🟠🟡🟢📊🚨💉🧰🚑👨‍⚕️💰🦟💧🇪🇹🇳🇬🇨🇩]/gu, '')
            .replace(/[═╔╗╚╝║]/g, '')
            .replace(/\s+/g, ' ')
            .trim();

        const utterance     = new SpeechSynthesisUtterance(cleanText);
        utterance.lang      = lang || currentLang;
        utterance.rate      = 0.95;   // slightly slower = clearer
        utterance.pitch     = 1.0;
        utterance.volume    = 1.0;

        // Try to find a good voice for the language
        const voices = synth.getVoices();
        const match  = voices.find(v =>
            v.lang.startsWith(utterance.lang.split('-')[0])
        );
        if (match) utterance.voice = match;

        synth.speak(utterance);
    }

    function replayLastResponse() {
        if (lastResponse) {
            speak(lastResponse);
        } else {
            speak('No previous response to replay.');
        }
    }

    // ============================================
    // LANGUAGE SELECTOR
    // ============================================
    function setLang(lang) {
        currentLang = lang;
        // Update button styles
        document.querySelectorAll('.lang-btn').forEach(btn => {
            btn.style.background = 'transparent';
            btn.style.color      = '#8B949E';
            btn.style.border     = '1px solid #30363D';
        });
        const mapping = {'en-US':'lang-en','fr-FR':'lang-fr','sw':'lang-sw'};
        const activeBtn = document.getElementById(mapping[lang]);
        if (activeBtn) {
            activeBtn.style.background = '#0A7B6E22';
            activeBtn.style.color      = '#0A7B6E';
            activeBtn.style.border     = '1px solid #0A7B6E55';
        }
        speak(`Language set to ${lang === 'en-US' ?
            'English' : lang === 'fr-FR' ?
            'French' : 'Kiswahili'}`);
    }

    // ============================================
    // SPEECH RECOGNITION (MIC INPUT)
    // ============================================
    function initRecognition() {
        const SR = window.SpeechRecognition ||
                   window.webkitSpeechRecognition;

        if (!SR) {
            document.getElementById('response-area').innerHTML =
                '⚠️ Speech recognition requires Chrome or Edge browser. ' +
                'Please use the text input or quick command buttons instead.';
            return false;
        }

        recognition                 = new SR();
        recognition.continuous      = false;
        recognition.interimResults  = true;
        recognition.lang            = currentLang;
        recognition.maxAlternatives = 1;

        recognition.onresult = (event) => {
            let transcript = '';
            let isFinal    = false;

            for (let i = event.resultIndex; i < event.results.length; i++) {
                transcript = event.results[i][0].transcript;
                isFinal    = event.results[i].isFinal;
            }

            setTranscript(
                (isFinal ? '✅ ' : '🎤 ') + transcript
            );

            if (isFinal) {
                stopListening();
                sendQuery(transcript);
            }
        };

        recognition.onerror = (event) => {
            stopListening();
            const errors = {
                'not-allowed': '🎤 Microphone blocked. Allow access in browser.',
                'no-speech':   '🔇 Nothing heard. Please try again.',
                'network':     '🌐 Network error. Check your connection.',
                'aborted':     '⏹ Listening stopped.',
            };
            setResponse(errors[event.error] ||
                `Speech error: ${event.error}`);
        };

        recognition.onend = () => {
            if (isListening) stopListening();
        };

        return true;
    }

    function startListening() {
        if (!recognition && !initRecognition()) return;

        // Stop any ongoing speech when user starts talking
        synth.cancel();

        isListening = true;
        try {
            recognition.lang = currentLang;
            recognition.start();
        } catch(e) {
            // Already started — ignore
        }

        // Visual: mic button turns red
        const btn = document.getElementById('mic-btn');
        btn.style.background = 'linear-gradient(135deg, #E8402A, #c0321e)';
        btn.style.boxShadow  = '0 4px 20px rgba(232,64,42,0.5)';
        btn.textContent      = '🔴 Listening...';

        setStatus('🔴 Listening', '#E8402A');
        setResponse(
            '<span style="color:#8B949E; font-style:italic;">' +
            '🎤 Speak now... Release button when done.</span>'
        );
    }

    function stopListening() {
        isListening = false;
        if (recognition) {
            try { recognition.stop(); } catch(e) {}
        }

        const btn = document.getElementById('mic-btn');
        btn.style.background = 'linear-gradient(135deg, #F5A623, #e0941a)';
        btn.style.boxShadow  = '0 4px 16px rgba(245,166,35,0.3)';
        btn.textContent      = '🎤 Hold to Speak';

        setStatus('Ready', '#2E7D52');
    }

    // ============================================
    // TEXT INPUT
    // ============================================
    function sendTextQuery() {
        const input = document.getElementById('text-input');
        const text  = input.value.trim();
        if (!text) return;
        setTranscript('✅ ' + text);
        sendQuery(text);
        input.value = '';
    }

    function quickQuery(text) {
        setTranscript('⚡ ' + text);
        sendQuery(text);
    }

    // ============================================
    // SEND QUERY TO API
    // ============================================
    function sendQuery(queryText) {
        setStatus('⚙️ Processing', '#F5A623');
        setResponse(
            '<span style="color:#8B949E;">⚙️ Analysing query...</span>'
        );

        fetch(`${API_BASE}/api/voice-query?q=${encodeURIComponent(queryText)}`)
            .then(r => {
                if (!r.ok) throw new Error(`API error: ${r.status}`);
                return r.json();
            })
            .then(data => {
                const response = data.response || 'No response available.';
                const intent   = data.intent   || 'unknown';
                const results  = data.data      || [];

                // Save for replay
                lastResponse = response;

                // Build results table HTML
                let tableHTML = '';
                if (results.length > 0 && results[0].region) {
                    tableHTML += `
                    <div style="margin-top:14px; border-top:1px solid #30363D;
                                padding-top:12px;">
                        <div style="font-size:11px; color:#8B949E;
                                    letter-spacing:1px; margin-bottom:8px;">
                            TOP RESULTS
                        </div>`;
                    results.slice(0, 5).forEach(r => {
                        const risk   = r.risk_score || 0;
                        const rColor = risk >= 75 ? '#E8402A' :
                                       risk >= 55 ? '#F5A623' : '#2E7D52';
                        tableHTML += `
                        <div style="display:flex; justify-content:space-between;
                                    align-items:center;
                                    padding:8px 0;
                                    border-bottom:1px solid #30363D22;">
                            <div>
                                <span style="color:#E8EDF3; font-weight:600;">
                                    ${r.region || ''}</span>
                                <span style="color:#8B949E; font-size:12px;">
                                    , ${r.country || ''}</span>
                            </div>
                            <div style="display:flex; gap:12px;
                                        align-items:center;">
                                <span style="color:#8B949E; font-size:12px;">
                                    ${r.top_disease || ''}
                                </span>
                                <span style="color:${rColor}; font-weight:700;
                                             font-size:15px;">
                                    ${risk.toFixed(0)}/100
                                </span>
                            </div>
                        </div>`;
                    });
                    tableHTML += '</div>';
                }

                // Intent badge color
                const intentColors = {
                    'high_risk_regions': '#E8402A',
                    'disease_query':     '#F5A623',
                    'country_query':     '#4A90D9',
                    'cross_border':      '#9B59B6',
                    'summary':           '#2E7D52',
                    'unknown':           '#8B949E'
                };
                const iColor = intentColors[intent] || '#8B949E';

                setResponse(`
                    <div style="display:flex; align-items:center;
                                gap:8px; margin-bottom:12px;">
                        <div style="background:${iColor}22;
                                    color:${iColor};
                                    border:1px solid ${iColor}44;
                                    border-radius:6px;
                                    padding:3px 10px;
                                    font-size:11px;
                                    letter-spacing:1px;
                                    text-transform:uppercase;">
                            ${intent.replace(/_/g, ' ')}
                        </div>
                    </div>
                    <div style="font-size:15px; line-height:1.7;
                                color:#E8EDF3;">
                        🧠 ${response}
                    </div>
                    ${tableHTML}
                `);

                // Speak the response
                speak(response);
                setStatus('Ready', '#2E7D52');
            })
            .catch(err => {
                const msg = 'Could not connect to AfyaMetrix API. ' +
                            'Please ensure the server is running on port 8000.';
                setResponse(`❌ ${msg}`);
                speak(msg);
                setStatus('Error', '#E8402A');
            });
    }

    // ============================================
    // UI HELPERS
    // ============================================
    function setResponse(html) {
        document.getElementById('response-area').innerHTML = html;
    }

    function setTranscript(text) {
        document.getElementById('transcript-text').textContent = text;
    }

    function setStatus(text, color) {
        document.getElementById('status-text').textContent  = text;
        document.getElementById('status-text').style.color  = color;
        document.getElementById('status-dot').style.background  = color;
        document.getElementById('status-dot').style.boxShadow   =
            `0 0 8px ${color}`;
    }

    function clearAll() {
        synth.cancel();
        setResponse(
            '<span style="color:#8B949E;">Ready for your next query...</span>'
        );
        setTranscript('Your words will appear here...');
        lastResponse = '';
    }

    // Init voices (Chrome needs this trigger)
    if (synth) {
        synth.getVoices();
        synth.onvoiceschanged = () => synth.getVoices();
    }

    // Init speech recognition
    initRecognition();
    </script>
    """

    st.components.v1.html(voice_html, height=780, scrolling=False)

    st.divider()
    st.markdown("""
    **How to use:**
    - **Hold the orange button** and speak — release when done
    - **🔊 button** replays the last spoken response
    - **Type** in the text box and press Enter or Ask
    - **Quick Commands** trigger common queries instantly
    - Works best in **Chrome or Edge** browser

    **Supported queries:**
    `show high risk regions` · `malaria status` · `cholera outbreak` ·  
    `cross border alerts` · `give me an overview` · `Kenya status` ·  
    `Nigeria update` · `Ethiopia health update` · `DRC critical alert`
    """)

# ========================================
# PAGE: DATA QUALITY
# ========================================

elif page == "📊 Data Quality":
    
    st.markdown("## 📊 Data Quality Dashboard")
    st.markdown(
        "*Ranking health facilities by reporting quality. "
        "Better data = better decisions.*"
    )
    
    quality = DATA['quality'].copy()
    
    if quality.empty:
        st.error("Quality data not available")
    else:
        if selected_countries:
            quality = quality[quality['country'].isin(selected_countries)]
        
        # Grade distribution
        col1, col2, col3, col4 = st.columns(4)
        for col, grade, color in zip(
            [col1, col2, col3, col4],
            ['A', 'B', 'C', 'D'],
            ['#2E7D52', '#F5A623', '#E8402A', '#8B0000']
        ):
            with col:
                count = len(quality[quality['quality_grade'] == grade])
                st.metric(f"Grade {grade}", count)
        
        st.divider()
        
        # Quality scores chart
        fig = px.bar(
            quality.sort_values('quality_score', ascending=True),
            x='quality_score',
            y='region',
            color='quality_grade',
            orientation='h',
            color_discrete_map={
                'A': '#2E7D52',
                'B': '#F5A623',
                'C': '#E8402A',
                'D': '#8B0000'
            },
            title='Data Quality Score by Region',
            template='plotly_dark',
            height=max(400, len(quality) * 15)
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#E8EDF3',
            margin=dict(l=0, r=0, t=40, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Full table
        st.dataframe(
            quality[[
                'country', 'region', 'quality_score',
                'quality_grade', 'completeness_pct', 'anomaly_rate_pct'
            ]].sort_values('quality_score', ascending=False),
            use_container_width=True,
            hide_index=True
        )