# ========================================
# AfyaMetrix FastAPI Backend
# File: api/main.py
# ========================================
#
# This file creates a web server with endpoints that
# the frontend dashboard calls to get data.
#
# Each endpoint is a URL that returns JSON data.
# Example: GET /api/risk-scores → returns risk scores for all regions
#
# Your frontend team calls these URLs using fetch() or axios.
# Your mobile app calls them too.
# Even the voice assistant calls them.

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json

# ========================================
# APP INITIALIZATION
# ========================================

app = FastAPI(
    title="AfyaMetrix API",
    description=(
        "Pan-Africa Public Health Intelligence Platform. "
        "Provides real-time risk scores, anomaly detection, "
        "forecasts, resource allocation, and health narratives "
        "for 10 African countries and 68 regions."
    ),
    version="1.0.0",
    docs_url="/docs",       # Swagger UI at /docs
    redoc_url="/redoc"      # ReDoc UI at /redoc
)

# ========================================
# CORS MIDDLEWARE
# ========================================
# CORS = Cross-Origin Resource Sharing
# This allows your frontend (running on a different port)
# to call this API without being blocked by the browser.
# Without this, your React dashboard can't talk to the API.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================================
# DATA LOADING
# ========================================
# We load all CSV files once when the server starts.
# This is called "caching" — much faster than reading
# files on every single API request.
DATA_PATH = r"C:\Users\admin\afyametrix-backend\data\processed"

def load_data():
    """Load all processed datasets into memory."""
    data = {}
    
    files = {
        'regional_risk':    'regional_risk_summary.csv',
        'clusters':         'region_clusters.csv',
        'forecasts':        'forecast_summary.csv',
        'allocations':      'resource_allocations.csv',
        'cross_border':     'cross_border_alerts.csv',
        'quality_scores':   'data_quality_scores.csv',
        'narratives':       'region_narratives.csv',
    }
    
    for key, filename in files.items():
        path = os.path.join(DATA_PATH, filename)
        try:
            df = pd.read_csv(path)
            # Convert date columns
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            data[key] = df
            print(f"  ✅ Loaded {filename}: {len(df):,} rows")
        except Exception as e:
            print(f"  ⚠️  Could not load {filename}: {e}")
            data[key] = pd.DataFrame()
    
    return data

print("🔄 Loading AfyaMetrix datasets...")
DATA = load_data()
print(f"✅ API ready with {len(DATA)} datasets loaded\n")

# Helper: convert DataFrame to clean JSON
def df_to_json(df, max_rows=None):
    if df is None or len(df) == 0:
        return []
    if max_rows:
        df = df.head(max_rows)
    # Replace NaN with None (JSON-safe)
    df = df.where(pd.notnull(df), None)
    return json.loads(df.to_json(orient='records', date_format='iso'))


# ========================================
# ENDPOINT 1: HEALTH CHECK
# ========================================

@app.get("/")
def root():
    """
    Root endpoint — confirms API is running.
    Frontend calls this to verify connection.
    """
    return {
        "status":    "✅ AfyaMetrix API is running",
        "version":   "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "datasets_loaded": {
            key: len(df) for key, df in DATA.items()
        }
    }


@app.get("/api/health")
def health_check():
    """Simple health check for monitoring systems."""
    return {
        "status":  "healthy",
        "time":    datetime.now().isoformat(),
        "regions": len(DATA['clusters'])
    }


# ========================================
# ENDPOINT 2: RISK SCORES
# ========================================

@app.get("/api/risk-scores")
def get_risk_scores(
    country:  str  = Query(None, description="Filter by country name"),
    date:     str  = Query(None, description="Specific date YYYY-MM-DD"),
    min_risk: float = Query(0,   description="Minimum risk score (0-100)"),
    limit:    int  = Query(100,  description="Max records to return")
):
    """
    Returns risk scores for all regions.
    
    This is the main endpoint for the dashboard heatmap.
    The frontend calls this to color regions by risk level.
    
    Examples:
    - /api/risk-scores → all regions, latest date
    - /api/risk-scores?country=Kenya → Kenya only
    - /api/risk-scores?min_risk=70 → only high-risk regions
    - /api/risk-scores?date=2024-06-15 → specific historical date
    """
    df = DATA['regional_risk'].copy()
    
    if df.empty:
        raise HTTPException(status_code=503, detail="Risk data not available")
    
    # Default to latest date
    if date:
        try:
            filter_date = pd.to_datetime(date)
            df = df[df['date'] == filter_date]
        except:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
    else:
        latest = df['date'].max()
        df = df[df['date'] == latest]
    
    # Apply filters
    if country:
        df = df[df['country'].str.lower() == country.lower()]
    
    df = df[df['risk_score'] >= min_risk]
    
    # Merge cluster labels
    if not DATA['clusters'].empty:
        df = df.merge(
            DATA['clusters'][[
                'country', 'region', 'cluster_label',
                'intervention_priority', 'resource_multiplier'
            ]],
            on=['country', 'region'],
            how='left'
        )
    
    # Sort by risk score descending
    df = df.sort_values('risk_score', ascending=False).head(limit)
    
    return {
        "date":         df['date'].iloc[0].isoformat() if len(df) > 0 else None,
        "total_regions": len(df),
        "data":         df_to_json(df)
    }


# ========================================
# ENDPOINT 3: ALERTS
# ========================================

@app.get("/api/alerts")
def get_alerts(
    country:   str = Query(None, description="Filter by country"),
    min_score: float = Query(55, description="Minimum risk score for alerts"),
    limit:     int  = Query(50,  description="Max alerts to return")
):
    """
    Returns active outbreak alerts.
    
    The dashboard alert panel calls this endpoint.
    Shows the red alert cards at the top of the CHL dashboard.
    
    Examples:
    - /api/alerts → all active alerts
    - /api/alerts?country=Nigeria → Nigeria alerts only
    - /api/alerts?min_score=75 → critical alerts only
    """
    df = DATA['regional_risk'].copy()
    
    if df.empty:
        return {"alerts": [], "total": 0}
    
    # Latest date only
    latest = df['date'].max()
    df = df[df['date'] == latest]
    
    # Filter to high-risk regions with active alerts
    alerts = df[
        (df['risk_score'] >= min_score) |
        (df['active_alerts'] > 0)
    ].copy()
    
    if country:
        alerts = alerts[alerts['country'].str.lower() == country.lower()]
    
    alerts = alerts.sort_values('risk_score', ascending=False).head(limit)
    
    # Format as alert objects
    alert_list = []
    for _, row in alerts.iterrows():
        
        risk  = row['risk_score']
        level = (
            'CRITICAL' if risk >= 75 else
            'HIGH'     if risk >= 55 else
            'MEDIUM'   if risk >= 30 else
            'LOW'
        )
        color = {
            'CRITICAL': '#E8402A',
            'HIGH':     '#F5A623',
            'MEDIUM':   '#FFD700',
            'LOW':      '#2E7D52'
        }[level]
        
        alert_list.append({
            "id":           f"{row['country']}-{row['region']}-{latest.date()}",
            "country":      row['country'],
            "region":       row['region'],
            "risk_score":   round(risk, 1),
            "alert_level":  level,
            "color":        color,
            "total_cases":  int(row.get('total_cases', 0)),
            "active_alerts": int(row.get('active_alerts', 0)),
            "top_disease":  row.get('top_disease', 'Unknown'),
            "timestamp":    latest.isoformat(),
            "message": (
                f"{row.get('top_disease', 'Disease')} alert in "
                f"{row['region']}, {row['country']}. "
                f"Risk score: {risk:.0f}/100."
            )
        })
    
    return {
        "total":      len(alert_list),
        "generated":  datetime.now().isoformat(),
        "alerts":     alert_list
    }


# ========================================
# ENDPOINT 4: FORECASTS
# ========================================

@app.get("/api/forecasts")
def get_forecasts(
    country: str = Query(None, description="Filter by country"),
    disease: str = Query(None, description="Filter by disease"),
    trend:   str = Query(None, description="Filter by trend: increasing/decreasing")
):
    """
    Returns 30-day disease forecasts.
    
    The trends chart on the CHL dashboard calls this.
    
    Examples:
    - /api/forecasts → all forecasts
    - /api/forecasts?country=Nigeria → Nigeria forecasts
    - /api/forecasts?trend=increasing → only worsening situations
    """
    df = DATA['forecasts'].copy()
    
    if df.empty:
        return {"forecasts": [], "total": 0}
    
    if country:
        df = df[df['country'].str.lower() == country.lower()]
    
    if disease:
        df = df[df['disease'].str.lower() == disease.lower()]
    
    if trend:
        if trend.lower() == 'increasing':
            df = df[df['trend_direction'].str.contains('Increasing')]
        elif trend.lower() == 'decreasing':
            df = df[df['trend_direction'].str.contains('Decreasing')]
    
    df = df.sort_values('model_confidence_pct', ascending=False)
    
    return {
        "total":     len(df),
        "forecasts": df_to_json(df)
    }


# ========================================
# ENDPOINT 5: RESOURCE ALLOCATIONS
# ========================================

@app.get("/api/allocations")
def get_allocations(
    country:  str = Query(None, description="Filter by country"),
    resource: str = Query(None, description="Resource type: vaccines/ambulances/budget_usd etc")
):
    """
    Returns recommended resource allocations per region.
    
    The resource planning panel calls this.
    
    Examples:
    - /api/allocations → all allocations
    - /api/allocations?country=Kenya → Kenya only
    - /api/allocations?resource=vaccines → vaccine allocations only
    """
    df = DATA['allocations'].copy()
    
    if df.empty:
        return {"allocations": [], "total": 0}
    
    if country:
        df = df[df['country'].str.lower() == country.lower()]
    
    if resource:
        # resource_allocations.csv has resources as columns
        if resource in df.columns:
            result = df[['country', 'region', 'risk_score', 
                         'cluster_label', resource]].copy()
            result = result.rename(columns={resource: 'allocated_amount'})
            result['resource_type'] = resource
            return {
                "resource_type": resource,
                "total":         len(result),
                "allocations":   df_to_json(
                    result.sort_values('allocated_amount', ascending=False)
                )
            }
    
    return {
        "total":       len(df),
        "allocations": df_to_json(
            df.sort_values('risk_score', ascending=False)
        )
    }


# ========================================
# ENDPOINT 6: NARRATIVE / AI BRIEF
# ========================================

@app.get("/api/narrative")
def get_narrative(
    country:  str = Query(..., description="Country name (required)"),
    region:   str = Query(..., description="Region name (required)"),
    language: str = Query("en", description="Language code: en/fr/sw")
):
    """
    Returns AI-generated health intelligence narrative for a region.
    
    The insight panel on the dashboard calls this.
    Non-technical health officials read these summaries.
    
    Examples:
    - /api/narrative?country=Kenya&region=Nairobi
    - /api/narrative?country=Senegal&region=Dakar&language=fr
    """
    df = DATA['narratives'].copy()
    
    if df.empty:
        raise HTTPException(status_code=503, detail="Narrative data not available")
    
    # Find matching region
    match = df[
        (df['country'].str.lower() == country.lower()) &
        (df['region'].str.lower() == region.lower())
    ]
    
    if len(match) == 0:
        # Generate a basic narrative if not pre-generated
        risk_df = DATA['regional_risk']
        latest  = risk_df['date'].max()
        region_data = risk_df[
            (risk_df['date'] == latest) &
            (risk_df['country'].str.lower() == country.lower()) &
            (risk_df['region'].str.lower() == region.lower())
        ]
        
        if len(region_data) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Region '{region}' in '{country}' not found"
            )
        
        row = region_data.iloc[0]
        return {
            "country":  country,
            "region":   region,
            "language": language,
            "narrative": (
                f"Health status for {region}, {country}: "
                f"Risk score {row['risk_score']:.0f}/100. "
                f"Primary disease: {row.get('top_disease', 'Unknown')}. "
                f"Total cases: {int(row.get('total_cases', 0)):,}. "
                f"Active alerts: {int(row.get('active_alerts', 0))}."
            )
        }
    
    row      = match.iloc[0]
    lang_col = f'narrative_{language}' if f'narrative_{language}' in row.index else 'narrative_en'
    
    return {
        "country":   country,
        "region":    region,
        "language":  language,
        "risk_score": float(row.get('risk_score', 0)),
        "narrative":  row.get(lang_col, row.get('narrative_en', 'No narrative available'))
    }


# ========================================
# ENDPOINT 7: CROSS-BORDER ALERTS
# ========================================

@app.get("/api/cross-border-alerts")
def get_cross_border_alerts(
    country: str = Query(None, description="Filter by source OR target country"),
    disease: str = Query(None, description="Filter by disease")
):
    """
    Returns active cross-border disease spread alerts.
    
    Shows which countries need to prepare because a
    neighboring country has an active outbreak.
    
    Examples:
    - /api/cross-border-alerts → all alerts
    - /api/cross-border-alerts?country=Kenya → alerts affecting Kenya
    """
    df = DATA['cross_border'].copy()
    
    if df.empty:
        return {"alerts": [], "total": 0}
    
    if country:
        df = df[
            (df['source_country'].str.lower() == country.lower()) |
            (df['target_country'].str.lower() == country.lower())
        ]
    
    if disease:
        df = df[df['disease'].str.lower() == disease.lower()]
    
    df = df.sort_values('source_risk_score', ascending=False)
    
    return {
        "total":  len(df),
        "alerts": df_to_json(df)
    }


# ========================================
# ENDPOINT 8: CLUSTERS
# ========================================

@app.get("/api/clusters")
def get_clusters(
    cluster: str = Query(None, description="Filter by cluster label")
):
    """
    Returns region cluster classifications and intervention plans.
    
    Examples:
    - /api/clusters → all regions with cluster labels
    - /api/clusters?cluster=Critical → only critical hotspots
    """
    df = DATA['clusters'].copy()
    
    if df.empty:
        return {"clusters": [], "total": 0}
    
    if cluster:
        df = df[df['cluster_label'].str.lower().str.contains(
            cluster.lower()
        )]
    
    df = df.sort_values('max_risk_score', ascending=False)
    
    return {
        "total":    len(df),
        "clusters": df_to_json(df[[
            'country', 'region', 'cluster_label',
            'intervention_priority', 'resource_multiplier',
            'avg_risk_score', 'max_risk_score',
            'outbreak_frequency', 'cases_per_100k'
        ]])
    }


# ========================================
# ENDPOINT 9: DATA QUALITY
# ========================================

@app.get("/api/data-quality")
def get_data_quality(
    country: str = Query(None, description="Filter by country"),
    grade:   str = Query(None, description="Filter by grade: A/B/C/D")
):
    """
    Returns data quality scores per region.
    
    The admin panel uses this to identify facilities
    that need reporting improvement.
    """
    df = DATA['quality_scores'].copy()
    
    if df.empty:
        return {"scores": [], "total": 0}
    
    if country:
        df = df[df['country'].str.lower() == country.lower()]
    
    if grade:
        df = df[df['quality_grade'] == grade.upper()]
    
    return {
        "total":  len(df),
        "scores": df_to_json(df)
    }


# ========================================
# ENDPOINT 10: SMS REPORT PARSER
# ========================================

@app.post("/api/sms-report")
def parse_sms_report(sms_text: str = Query(..., description="SMS text to parse")):
    """
    Parses an SMS report from a Community Health Worker.
    
    Format: DISEASE_CODE CASES AREA_CODE [URGENT] [#CHW_NAME]
    Example: MAL 12 KE047 URGENT #John
    
    Returns structured health data extracted from the SMS.
    """
    SMS_DISEASE_CODES = {
        'MAL': 'Malaria',       'COL': 'Cholera',
        'TUB': 'Tuberculosis',  'MEN': 'Meningitis',
        'TYP': 'Typhoid',       'MPX': 'Mpox',
        'DEN': 'Dengue',        'RES': 'Respiratory_Infections',
        'DIA': 'Diarrheal_Disease', 'MNT': 'Malnutrition'
    }
    COUNTRY_CODES = {
        'KE': 'Kenya',    'NG': 'Nigeria',  'ET': 'Ethiopia',
        'UG': 'Uganda',   'TZ': 'Tanzania', 'GH': 'Ghana',
        'SN': 'Senegal',  'CD': 'DRC',      'ZM': 'Zambia',
        'SD': 'Sudan'
    }
    
    parts = sms_text.strip().upper().split()
    
    if len(parts) < 3:
        raise HTTPException(
            status_code=400,
            detail="Too few parts. Format: DISEASE CASES AREA_CODE"
        )
    
    disease_code = parts[0]
    if disease_code not in SMS_DISEASE_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown disease code: {disease_code}"
        )
    
    try:
        cases = int(parts[1])
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid case count: {parts[1]}"
        )
    
    area_code    = parts[2]
    country_code = area_code[:2]
    
    return {
        "valid":     True,
        "disease":   SMS_DISEASE_CODES[disease_code],
        "cases":     cases,
        "area_code": area_code,
        "country":   COUNTRY_CODES.get(country_code, 'Unknown'),
        "urgent":    'URGENT' in parts,
        "chw_tag":   next((p[1:] for p in parts if p.startswith('#')), None),
        "timestamp": datetime.now().isoformat()
    }


# ========================================
# ENDPOINT 11: VOICE ASSISTANT QUERY
# ========================================

@app.get("/api/voice-query")
def voice_query(q: str = Query(..., description="Voice query text")):
    """
    Processes natural language voice queries and returns data.
    
    The voice assistant sends the transcribed text here.
    Simple keyword matching routes to the right data.
    
    Examples:
    - /api/voice-query?q=show high risk regions
    - /api/voice-query?q=malaria in Kenya
    - /api/voice-query?q=cross border alerts
    """
    query     = q.lower().strip()
    risk_df   = DATA['regional_risk']
    latest    = risk_df['date'].max()
    latest_df = risk_df[risk_df['date'] == latest]
    
    # ---- INTENT: High risk regions ----
    if any(word in query for word in ['high risk', 'critical', 'dangerous', 'worst']):
        results = latest_df.nlargest(5, 'risk_score')
        regions = [
            f"{r['region']}, {r['country']} (risk: {r['risk_score']:.0f})"
            for _, r in results.iterrows()
        ]
        return {
            "intent":   "high_risk_regions",
            "response": f"The 5 highest risk regions are: {'; '.join(regions)}.",
            "data":     df_to_json(results)
        }
    
    # ---- INTENT: Specific disease ----
    diseases = [
        'malaria', 'cholera', 'tuberculosis', 'meningitis',
        'typhoid', 'mpox', 'dengue'
    ]
    matched_disease = next(
        (d for d in diseases if d in query), None
    )
    if matched_disease:
        disease_df = latest_df[
            latest_df['top_disease'].str.lower() == matched_disease
        ].nlargest(3, 'risk_score')
        
        if len(disease_df) > 0:
            regions = [
                f"{r['region']}, {r['country']}"
                for _, r in disease_df.iterrows()
            ]
            return {
                "intent":   "disease_query",
                "disease":  matched_disease,
                "response": (
                    f"{matched_disease.title()} is most active in: "
                    f"{'; '.join(regions)}."
                ),
                "data": df_to_json(disease_df)
            }
    
    # ---- INTENT: Specific country ----
    countries = [
        'kenya', 'nigeria', 'ethiopia', 'uganda',
        'tanzania', 'ghana', 'senegal', 'drc', 'zambia', 'sudan'
    ]
    matched_country = next(
        (c for c in countries if c in query), None
    )
    if matched_country:
        country_df = latest_df[
            latest_df['country'].str.lower() == matched_country
        ].nlargest(3, 'risk_score')
        avg_risk = country_df['risk_score'].mean()
        return {
            "intent":   "country_query",
            "country":  matched_country,
            "response": (
                f"{matched_country.title()} has an average risk score of "
                f"{avg_risk:.0f}/100."
            ),
            "data": df_to_json(country_df)
        }
    
    # ---- INTENT: Cross-border alerts ----
    if any(word in query for word in ['border', 'spread', 'neighboring', 'cross']):
        alerts_df = DATA['cross_border']
        return {
            "intent":   "cross_border",
            "response": f"There are {len(alerts_df)} active cross-border alerts.",
            "data":     df_to_json(alerts_df.head(5))
        }
    
    # ---- INTENT: Summary / overview ----
    if any(word in query for word in ['summary', 'overview', 'status', 'update']):
        critical = latest_df[latest_df['risk_score'] >= 75]
        high     = latest_df[latest_df['risk_score'] >= 55]
        return {
            "intent":   "summary",
            "response": (
                f"AfyaMetrix status update: "
                f"{len(critical)} critical regions, "
                f"{len(high)} high-risk regions across "
                f"{latest_df['country'].nunique()} countries. "
                f"Latest data from {latest.date()}."
            ),
            "data": df_to_json(latest_df.nlargest(5, 'risk_score'))
        }
    
    # ---- DEFAULT: Unknown intent ----
    return {
        "intent":   "unknown",
        "response": (
            "I can help with: high risk regions, disease status, "
            "country overview, cross-border alerts, or a general summary."
        ),
        "data": []
    }


# ========================================
# ENDPOINT 12: DASHBOARD SUMMARY
# ========================================

@app.get("/api/dashboard-summary")
def get_dashboard_summary(
    country: str = Query(None, description="Filter by country")
):
    """
    Returns a complete summary object for the main dashboard.
    
    The frontend calls this ONCE on page load to get
    everything it needs to render the initial view.
    This reduces the number of API calls needed.
    """
    risk_df  = DATA['regional_risk']
    latest   = risk_df['date'].max()
    snap     = risk_df[risk_df['date'] == latest]
    
    if country:
        snap = snap[snap['country'].str.lower() == country.lower()]
    
    cross = DATA['cross_border']
    
    return {
        "generated":          datetime.now().isoformat(),
        "data_as_of":         latest.isoformat(),
        "coverage": {
            "countries":      int(snap['country'].nunique()),
            "regions":        int(len(snap)),
        },
        "risk_summary": {
            "critical":       int((snap['risk_score'] >= 75).sum()),
            "high":           int(((snap['risk_score'] >= 55) & 
                                   (snap['risk_score'] < 75)).sum()),
            "medium":         int(((snap['risk_score'] >= 30) & 
                                   (snap['risk_score'] < 55)).sum()),
            "low":            int((snap['risk_score'] < 30).sum()),
            "avg_risk_score": round(float(snap['risk_score'].mean()), 1),
        },
        "top_alerts":         df_to_json(
            snap.nlargest(5, 'risk_score')[[
                'country', 'region', 'risk_score', 
                'top_disease', 'active_alerts'
            ]]
        ),
        "cross_border_count": len(cross),
        "total_cases_today":  int(snap['total_cases'].sum()),
    }