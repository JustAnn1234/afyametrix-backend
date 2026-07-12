# AfyaMetrix — Pan-Africa Public Health Intelligence Platform
## AI/ML Engineering Module

**Author:** Omosomi Ann Hassan (AI/ML Engineer)  
**Programme:** AI/ML Engineering — Africa Agility (AGIT)  
**Project Type:** Group Capstone Project

---

## Project Overview

AfyaMetrix is a pan-Africa public health intelligence platform that uses machine learning to detect disease outbreaks, forecast trends, allocate resources, and generate multilingual health narratives across 10 African countries and 68 regions.

This repository contains the **AI/ML engineering module** — including all custom models, data pipelines, and the FastAPI backend that powers the platform.

---

## What's Inside

```
afyametrix/
├── api/
│   └── main.py              # FastAPI backend — 12+ endpoints
├── data/
│   ├── raw/
│   │   └── africa_health_simulated.csv
│   └── processed/           # All model outputs (CSV)
├── notebooks/
│   ├── 00_setup.ipynb               # Environment setup
│   ├── 01_data_simulation.ipynb     # Synthetic data generation
│   ├── 02_anomaly_detection.ipynb   # Z-Score + Isolation Forest
│   ├── 03_risk_scoring.ipynb        # Composite risk scoring
│   ├── 04_forecasting.ipynb         # Prophet time-series forecasting
│   ├── 05_clustering.ipynb          # K-Means clustering + maps
│   ├── 06_resource_allocation_narrative.ipynb
│   ├── 07_run_api.ipynb             # API testing
│   ├── 08_voice_assistant.ipynb     # Voice query interface
│   └── 09_shap_explainability.ipynb # SHAP explainability
├── models/saved/            # Trained model files
├── outputs/
│   ├── maps/
│   └── reports/
└── utils/                   # Helper functions
```

## AI/ML Models Built

| Model | Purpose | Library |
|-------|---------|---------|
| Isolation Forest | Anomaly detection in disease reports | scikit-learn |
| Z-Score Detection | Statistical spike identification | numpy/scipy |
| Prophet | 30-day disease outbreak forecasting | prophet |
| K-Means Clustering | Regional risk cluster classification | scikit-learn |
| SHAP Explainability | Model decision transparency | shap |
| Multilingual Narrative Engine | Auto-generates health briefs in EN/FR/SW/HA/AM | custom |

---

## FastAPI Backend

The backend exposes 14+ REST endpoints for the frontend to consume.

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/risk-scores` | GET | Risk scores for all regions |
| `/api/alerts` | GET | Active outbreak alerts |
| `/api/forecasts` | GET | 30-day disease forecasts |
| `/api/clusters` | GET | K-Means cluster classifications |
| `/api/narrative` | GET | AI-generated health narrative |
| `/api/cross-border-alerts` | GET | Cross-border spread alerts |
| `/api/dashboard-summary` | GET | Full dashboard summary |
| `/api/sms-report` | POST | Parse SMS from health workers |
| `/api/voice-query` | GET | Natural language voice queries |
| `/api/data-quality` | GET | Data quality scores per region |
| `/api/map-html` | GET | Plotly choropleth map as HTML |
| `/api/ask-vitara` | POST | AI clinical assistant (Groq/Llama) |
| `/api/generate-situation-report` | POST | AI weekly situation report |

Full API documentation available at `http://localhost:8000/docs` when running locally.

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- pip

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/afyametrix-backend.git
cd afyametrix-backend
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set environment variables
```bash
# Windows
set GROQ_KEY=your_groq_api_key_here

# Mac/Linux
export GROQ_KEY=your_groq_api_key_here
```

Get a free Groq API key at [console.groq.com](https://console.groq.com)

### 4. Run the notebooks (in order)
Open Jupyter and run notebooks `00` through `09` in sequence. Each notebook builds on the outputs of the previous one.

```bash
jupyter notebook
```

### 5. Start the API
```bash
cd api
uvicorn main:app --reload --port 8000
```

API will be available at `http://localhost:8000`  
Swagger docs at `http://localhost:8000/docs`

---

## Data

The platform uses **synthetic health data** modeled on real epidemiological patterns from NCDC, WHO, and Africa CDC reports. The data covers:

- 10 African countries: Nigeria, Kenya, Ethiopia, Uganda, Tanzania, Ghana, Senegal, DRC, Zambia, Sudan
- 68 regions
- 10 disease categories: Malaria, Cholera, Tuberculosis, Meningitis, Typhoid, Mpox, Dengue, Respiratory Infections, Diarrheal Disease, Malnutrition
- 49,708 data points spanning 2 years

---

## Requirements

Create a `requirements.txt` in the root with:
fastapi
uvicorn
pandas
numpy
httpx
groq
plotly
scikit-learn
prophet
shap
python-multipart
jupyter

---

## For the Frontend Developer

The API is CORS-enabled and ready to connect. Base URL when running locally: `http://localhost:8000`

All endpoints return JSON. See `/docs` for full request/response schemas.

Key endpoints you'll use most:
- `GET /api/dashboard-summary` — main dashboard stats
- `GET /api/alerts?country=Nigeria` — alert feed
- `GET /api/forecasts` — trend charts
- `GET /api/map-html` — interactive choropleth map
- `POST /api/ask-vitara` — AI chat `{"message": "...", "history": []}`
- `POST /api/generate-situation-report` — AI report `{}`

---

## Author Note

This AI/ML module was built as part of the AfyaMetrix capstone project for the Africa Agility AI/ML Engineering programme. The models, data pipeline, and API were designed and implemented by Omosomi Ann Hassan.

The platform is production-ready for integration with a real health data feed from NCDC or partner facilities.

---

*Built with Python · FastAPI · Prophet · scikit-learn · Plotly · Groq/Llama*
