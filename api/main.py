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

from fastapi import FastAPI, Query, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
from jose import JWTError, jwt
import uuid
import random
import re
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from email_service import send_verification_email, send_password_reset_email

# Load environment variables
load_dotenv()

# Load environment variables
load_dotenv()

# Get Groq API key
GROQ_API_KEY = os.getenv("GROQ_KEY")
if not GROQ_API_KEY:
    print("⚠️  WARNING: GROQ_KEY not found in environment variables")

# ========================================
# AUTHENTICATION CONFIGURATION
# ========================================

# Security settings
SECRET_KEY = "afyametrix-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()

# In-memory user storage (replace with database in production)
USERS_DB = {}
VERIFICATION_CODES = {}  # {email: {"code": "123456", "expires": datetime, "user_data": {}}}
PASSWORD_RESET_CODES = {}  # {email: {"code": "123456", "expires": datetime}}

# ========================================
# PYDANTIC MODELS
# ========================================

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field(..., pattern="^(CHW|Admin|Doctor|Analyst)$")

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class EmailVerification(BaseModel):
    email: EmailStr
    code: str = Field(..., pattern="^[0-9]{6}$")

class ForgotPassword(BaseModel):
    email: EmailStr

class ResetPassword(BaseModel):
    email: EmailStr
    code: str = Field(..., pattern="^[0-9]{6}$")
    new_password: str = Field(..., min_length=6, max_length=100)

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    verified: bool = False

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# ========================================
# AUTHENTICATION UTILITIES
# ========================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return user data."""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def generate_verification_code() -> str:
    """Generate 6-digit verification code."""
    return str(random.randint(100000, 999999))

def cleanup_expired_codes():
    """Remove expired verification codes."""
    current_time = datetime.utcnow()
    
    # Clean verification codes
    expired_emails = [
        email for email, data in VERIFICATION_CODES.items()
        if data["expires"] < current_time
    ]
    for email in expired_emails:
        del VERIFICATION_CODES[email]
    
    # Clean password reset codes
    expired_reset_emails = [
        email for email, data in PASSWORD_RESET_CODES.items()
        if data["expires"] < current_time
    ]
    for email in expired_reset_emails:
        del PASSWORD_RESET_CODES[email]

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
    allow_origins=["http://localhost:3000"],  # Frontend URL
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
    """Load datasets or create sample data if files don't exist."""
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
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            data[key] = df
            print(f"  ✅ Loaded {filename}: {len(df):,} rows")
        except Exception:
            print(f"  📝 Creating sample data for {filename}")
            data[key] = create_sample_data(key)
    
    return data

def create_sample_data(data_type):
    """Create sample data for API testing when real data isn't available."""
    if data_type == 'regional_risk':
        return pd.DataFrame({
            'date': pd.to_datetime(['2024-07-19'] * 5),
            'country': ['Kenya', 'Nigeria', 'Ethiopia', 'Uganda', 'Tanzania'],
            'region': ['Nairobi', 'Lagos', 'Addis Ababa', 'Kampala', 'Dar es Salaam'],
            'risk_score': [65.5, 78.2, 45.1, 52.3, 38.9],
            'total_cases': [1250, 2100, 850, 950, 720],
            'active_alerts': [2, 3, 1, 1, 0],
            'top_disease': ['Malaria', 'Cholera', 'TB', 'Malaria', 'Dengue']
        })
    elif data_type == 'cross_border':
        return pd.DataFrame({
            'source_country': ['Kenya', 'Nigeria'],
            'target_country': ['Uganda', 'Chad'],
            'disease': ['Malaria', 'Cholera'],
            'source_risk_score': [65.5, 78.2],
            'spread_probability': [75, 85]
        })
    elif data_type == 'forecasts':
        return pd.DataFrame({
            'country': ['Kenya', 'Nigeria'],
            'region': ['Nairobi', 'Lagos'],
            'disease': ['Malaria', 'Cholera'],
            'forecast_avg_daily_cases': [45, 78],
            'trend_direction': ['Increasing', 'Decreasing'],
            'model_confidence_pct': [85, 92]
        })
    else:
        return pd.DataFrame()

print("🔄 Loading AfyaMetrix datasets...")
DATA = load_data()
print(f"✅ API ready with {len(DATA)} datasets loaded\n")

# ========================================
# AUTHENTICATION ENDPOINTS
# ========================================

@app.post("/api/auth/register", status_code=201, response_model=dict)
def register_user(user: UserRegister):
    """
    Register a new user with email verification.
    
    Creates a user account and sends a verification code.
    User must verify email before they can login.
    """
    # Clean up expired codes first
    cleanup_expired_codes()
    
    # Validate email format
    if not validate_email(user.email):
        raise HTTPException(
            status_code=400,
            detail="Invalid email format"
        )
    
    # Check if user already exists
    if user.email in USERS_DB:
        raise HTTPException(
            status_code=409,
            detail="User with this email already exists"
        )
    
    # Validate password length
    if len(user.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters long"
        )
    
    # Validate role
    valid_roles = ["CHW", "Admin", "Doctor", "Analyst"]
    if user.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Role must be one of: {', '.join(valid_roles)}"
        )
    
    # Generate user ID and verification code
    user_id = str(uuid.uuid4())
    verification_code = generate_verification_code()
    
    # Store verification code (expires in 10 minutes)
    VERIFICATION_CODES[user.email] = {
        "code": verification_code,
        "expires": datetime.utcnow() + timedelta(minutes=10),
        "user_data": {
            "id": user_id,
            "name": user.name,
            "email": user.email,
            "password": get_password_hash(user.password),
            "role": user.role,
            "verified": False,
            "created_at": datetime.utcnow().isoformat()
        }
    }
    
    # Send verification email
    email_sent = send_verification_email(user.email, verification_code, user.name)
    
    if not email_sent:
        # Log verification code to console as fallback
        print(f"📧 FALLBACK: Verification code for {user.email} is {verification_code}")
        return {
            "message": "User registered successfully. Email service unavailable - check console for verification code.",
            "user": {
                "id": user_id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "verified": False
            }
        }
    
    return {
        "message": "User registered successfully. Please check your email for the verification code.",
        "user": {
            "id": user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "verified": False
        }
    }


@app.post("/api/auth/verify-email", response_model=dict)
def verify_email(verification: EmailVerification):
    """
    Verify user email with 6-digit code.
    
    After successful verification, user can login.
    """
    # Clean up expired codes first
    cleanup_expired_codes()
    
    # Check if verification code exists
    if verification.email not in VERIFICATION_CODES:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code"
        )
    
    stored_data = VERIFICATION_CODES[verification.email]
    
    # Verify code
    if stored_data["code"] != verification.code:
        raise HTTPException(
            status_code=400,
            detail="Invalid verification code"
        )
    
    # Check if code is expired
    if stored_data["expires"] < datetime.utcnow():
        del VERIFICATION_CODES[verification.email]
        raise HTTPException(
            status_code=400,
            detail="Verification code has expired"
        )
    
    # Move user to main database with verified status
    user_data = stored_data["user_data"]
    user_data["verified"] = True
    USERS_DB[verification.email] = user_data
    
    # Remove verification code
    del VERIFICATION_CODES[verification.email]
    
    print(f"✅ Email verified successfully for {verification.email}")
    
    return {
        "message": "Email verified successfully"
    }


@app.post("/api/auth/forgot-password", response_model=dict)
def forgot_password(request: ForgotPassword):
    """
    Send password reset code to user's email.
    
    If the email exists in the system, sends a 6-digit reset code.
    """
    # Clean up expired codes first
    cleanup_expired_codes()
    
    # Validate email format
    if not validate_email(request.email):
        raise HTTPException(
            status_code=400,
            detail="Invalid email format"
        )
    
    # Check if user exists and is verified
    if request.email not in USERS_DB:
        # Don't reveal if email exists or not for security
        return {
            "message": "If this email is registered, a password reset code has been sent."
        }
    
    user_data = USERS_DB[request.email]
    if not user_data.get("verified", False):
        return {
            "message": "Please verify your email address first before resetting password."
        }
    
    # Generate reset code
    reset_code = generate_verification_code()
    
    # Store reset code (expires in 15 minutes)
    PASSWORD_RESET_CODES[request.email] = {
        "code": reset_code,
        "expires": datetime.utcnow() + timedelta(minutes=15)
    }
    
    # Send reset email
    email_sent = send_password_reset_email(request.email, reset_code, user_data["name"])
    
    if not email_sent:
        # Log reset code to console as fallback
        print(f"🔒 FALLBACK: Password reset code for {request.email} is {reset_code}")
        return {
            "message": "Password reset requested. Email service unavailable - check console for reset code."
        }
    
    return {
        "message": "If this email is registered, a password reset code has been sent."
    }


@app.post("/api/auth/reset-password", response_model=dict)
def reset_password(reset_request: ResetPassword):
    """
    Reset user password with verification code.
    
    User must provide valid reset code received via email.
    """
    # Clean up expired codes first
    cleanup_expired_codes()
    
    # Validate email format
    if not validate_email(reset_request.email):
        raise HTTPException(
            status_code=400,
            detail="Invalid email format"
        )
    
    # Check if reset code exists
    if reset_request.email not in PASSWORD_RESET_CODES:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset code"
        )
    
    stored_code_data = PASSWORD_RESET_CODES[reset_request.email]
    
    # Verify reset code
    if stored_code_data["code"] != reset_request.code:
        raise HTTPException(
            status_code=400,
            detail="Invalid reset code"
        )
    
    # Check if code is expired
    if stored_code_data["expires"] < datetime.utcnow():
        del PASSWORD_RESET_CODES[reset_request.email]
        raise HTTPException(
            status_code=400,
            detail="Reset code has expired"
        )
    
    # Validate new password
    if len(reset_request.new_password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters long"
        )
    
    # Check if user still exists
    if reset_request.email not in USERS_DB:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    # Update password
    USERS_DB[reset_request.email]["password"] = get_password_hash(reset_request.new_password)
    
    # Remove reset code
    del PASSWORD_RESET_CODES[reset_request.email]
    
    print(f"🔒 Password reset successfully for {reset_request.email}")
    
    return {
        "message": "Password reset successfully. You can now login with your new password."
    }


@app.post("/api/auth/login", response_model=TokenResponse)
def login_user(user_credentials: UserLogin):
    """
    Login user and return JWT access token.
    
    User must have verified their email before login.
    """
    # Validate email format
    if not validate_email(user_credentials.email):
        raise HTTPException(
            status_code=400,
            detail="Invalid email format"
        )
    
    # Check if user exists
    if user_credentials.email not in USERS_DB:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    user_data = USERS_DB[user_credentials.email]
    
    # Check if email is verified
    if not user_data.get("verified", False):
        raise HTTPException(
            status_code=401,
            detail="Please verify your email before logging in"
        )
    
    # Verify password
    if not verify_password(user_credentials.password, user_data["password"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user_credentials.email, "user_id": user_data["id"]}
    )
    
    print(f"✅ User logged in successfully: {user_credentials.email}")
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user_data["id"],
            name=user_data["name"],
            email=user_data["email"],
            role=user_data["role"],
            verified=user_data["verified"]
        )
    )


@app.get("/api/auth/me", response_model=UserResponse)
def get_current_user(token_data: dict = Depends(verify_token)):
    """
    Get current user information from JWT token.
    
    Protected endpoint that requires valid JWT token.
    """
    email = token_data.get("sub")
    if email not in USERS_DB:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    user_data = USERS_DB[email]
    return UserResponse(
        id=user_data["id"],
        name=user_data["name"],
        email=user_data["email"],
        role=user_data["role"],
        verified=user_data["verified"]
    )


# ========================================
# PROTECTED ENDPOINT EXAMPLE
# ========================================

@app.get("/api/protected/dashboard")
def protected_dashboard(token_data: dict = Depends(verify_token)):
    """
    Example protected endpoint requiring authentication.
    
    Frontend can use this pattern for protected routes.
    """
    email = token_data.get("sub")
    user_id = token_data.get("user_id")
    
    return {
        "message": f"Welcome to protected dashboard, {email}!",
        "user_id": user_id,
        "data": "This is protected content",
        "timestamp": datetime.utcnow().isoformat()
    }

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