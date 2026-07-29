# ========================================
# AfyaMetrix Production Backend API
# File: api/main_production.py
# ========================================

from fastapi import FastAPI, Query, HTTPException, Depends, status, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json
import uuid
import random
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# Pydantic models
from pydantic import BaseModel, EmailStr, Field, validator

# Authentication
from passlib.context import CryptContext
from jose import JWTError, jwt

# Database
from api.database import (
    database, connect_db, disconnect_db, 
    users, notifications, cases, dashboard_alerts, verification_codes,
    get_user_by_email, get_user_by_id, create_user, update_user
)

# Email service
from api.email_service import email_service

# Load environment variables
load_dotenv()

# ========================================
# CONFIGURATION
# ========================================

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "afyametrix-super-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()

# In-memory storage for verification codes (use Redis in production)
VERIFICATION_CODES = {}
PASSWORD_RESET_CODES = {}

# ========================================
# HEALTH DATA LOADING (from original main.py)
# ========================================

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "processed")

def load_health_data():
    """Load health datasets or create sample data if files don't exist."""
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
            print(f"  📝 Creating sample health data for {filename}")
            data[key] = create_health_sample_data(key)
    
    return data

def create_health_sample_data(data_type):
    """Create sample health data for API testing when real data isn't available."""
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

# Helper: convert DataFrame to clean JSON
def df_to_json(df, max_rows=None):
    if df is None or len(df) == 0:
        return []
    if max_rows:
        df = df.head(max_rows)
    # Replace NaN with None (JSON-safe)
    df = df.where(pd.notnull(df), None)
    return json.loads(df.to_json(orient='records', date_format='iso'))

# Load health data
print("🔄 Loading AfyaMetrix health datasets...")
HEALTH_DATA = load_health_data()
print(f"✅ Health data loaded with {len(HEALTH_DATA)} datasets\n")

# ========================================
# FASTAPI APP INITIALIZATION
# ========================================

app = FastAPI(
    title="AfyaMetrix Production API",
    description="Last-Mile Health Surveillance Platform for African Community Health Workers",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_URL", "http://localhost:3000"),
        "https://afyametrix-frontend.netlify.app"  # Add your frontend URL directly
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================================
# PYDANTIC MODELS
# ========================================

# User models
class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field(..., pattern="^(CHW|Admin|Doctor|Analyst)$")
    location: Optional[str] = Field(None, max_length=255)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class EmailVerification(BaseModel):
    email: EmailStr
    code: str = Field(..., pattern="^[0-9]{6}$")

class UserProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    location: Optional[str] = Field(None, max_length=255)

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6, max_length=100)

class ForgotPassword(BaseModel):
    email: EmailStr

class ResetPassword(BaseModel):
    email: EmailStr
    code: str = Field(..., pattern="^[0-9]{6}$")
    new_password: str = Field(..., min_length=6, max_length=100)

class ResendVerification(BaseModel):
    email: EmailStr

class NotificationSettings(BaseModel):
    emailNotifications: bool = True
    smsAlerts: bool = False
    systemNotifications: bool = True

# Case models
class CaseCreate(BaseModel):
    diseaseType: str = Field(..., max_length=100)
    cases: int = Field(..., ge=0)
    caseDetails: Optional[str] = Field(None, max_length=2000)
    comments: Optional[str] = Field(None, max_length=1000)
    photos: Optional[List[str]] = Field(default_factory=list)

class SyncRequest(BaseModel):
    items: List[Dict[str, Any]]

# Response models
class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    location: Optional[str] = None
    verified: bool = False

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    message: str
    timestamp: str
    read: bool

class CaseResponse(BaseModel):
    id: str
    diseaseType: str
    cases: int
    date: str
    worker: str
    status: str
    caseDetails: Optional[str] = None
    comments: Optional[str] = None
    photos: List[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str

# ========================================
# AUTHENTICATION UTILITIES
# ========================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Use simple hash comparison for production compatibility
    import hashlib
    salt = "afyametrix_salt_2024"
    plain_hash = hashlib.sha256((plain_password + salt).encode()).hexdigest()
    return plain_hash == hashed_password

def get_password_hash(password: str) -> str:
    # Use SHA256 with salt instead of bcrypt for production compatibility
    import hashlib
    salt = "afyametrix_salt_2024"
    return hashlib.sha256((password + salt).encode()).hexdigest()

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        print(f"🔍 DEBUG: Received token: {credentials.credentials[:20]}...")
        
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        email: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        
        print(f"🔍 DEBUG: Decoded payload - email: {email}, user_id: {user_id}")
        
        if email is None:
            print("❌ DEBUG: Email is None in token payload")
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        user = await get_user_by_id(user_id)
        print(f"🔍 DEBUG: Database lookup result - user found: {user is not None}")
        
        if not user:
            print(f"❌ DEBUG: No user found with ID: {user_id}")
            raise HTTPException(status_code=401, detail="User not found")
        
        print(f"✅ DEBUG: Successfully authenticated user: {user.email}")
        return user
        
    except JWTError as e:
        print(f"❌ DEBUG: JWT decode error: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

def generate_verification_code() -> str:
    return str(random.randint(100000, 999999))

def cleanup_expired_codes():
    current_time = datetime.utcnow()
    # Clean verification codes
    expired_emails = [
        email for email, data in VERIFICATION_CODES.items()
        if data["expires"] < current_time
    ]
    for email in expired_emails:
        del VERIFICATION_CODES[email]
    
    # Clean password reset codes
    expired_emails = [
        email for email, data in PASSWORD_RESET_CODES.items()
        if data["expires"] < current_time
    ]
    for email in expired_emails:
        del PASSWORD_RESET_CODES[email]

# ========================================
# DATABASE EVENT HANDLERS
# ========================================

@app.on_event("startup")
async def startup():
    await connect_db()

@app.on_event("shutdown")
async def shutdown():
    await disconnect_db()

# ========================================
# AUTHENTICATION ENDPOINTS
# ========================================

@app.post("/api/auth/register", status_code=201)
@limiter.limit("5/minute")
async def register_user(request: Request, user: UserRegister, background_tasks: BackgroundTasks):
    # Check if user exists
    existing_user = await get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(status_code=409, detail="User with this email already exists")
    
    # Generate verification code
    verification_code = generate_verification_code()
    user_id = str(uuid.uuid4())
    
    user_data = {
        "id": user_id,
        "name": user.name,
        "email": user.email,
        "password": get_password_hash(user.password),
        "role": user.role,
        "location": user.location,
        "verified": False,
        "notification_settings": {
            "emailNotifications": True,
            "smsAlerts": False,
            "systemNotifications": True
        }
    }
    
    # Clean up any existing verification codes for this email first
    try:
        await database.execute(
            verification_codes.delete().where(verification_codes.c.email == user.email)
        )
        print(f"🧹 Cleaned existing verification codes for {user.email}")
    except Exception as e:
        print(f"⚠️ No existing codes to clean: {str(e)}")
    
    try:
        # Store in database with proper timezone handling
        from datetime import timezone
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)  # 15 minutes for testing
        
        await database.execute(
            verification_codes.insert().values(
                email=user.email,
                code=verification_code,
                expires_at=expires_at,
                user_data=user_data
            )
        )
        print("✅ Using database storage for verification codes")
        
        # Also store in memory as backup
        VERIFICATION_CODES[user.email] = {
            "code": verification_code,
            "expires": expires_at.replace(tzinfo=None),  # Store as naive datetime for memory
            "user_data": user_data
        }
        
    except Exception as e:
        # Fallback to memory storage only
        VERIFICATION_CODES[user.email] = {
            "code": verification_code,
            "expires": datetime.utcnow() + timedelta(minutes=15),
            "user_data": user_data
        }
        print(f"⚠️ Using memory storage only: {str(e)}")
    
    # DEBUG: Log verification code when email fails
    print(f"🔑 DEBUG: Verification code for {user.email}: {verification_code}")
    
    # Send verification email
    background_tasks.add_task(
        email_service.send_verification_email, 
        user.email, 
        verification_code, 
        user.name
    )
    
    return {
        "message": "User registered successfully. Please check your email for verification code.",
        "user": {
            "id": user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "verified": False
        }
    }

@app.post("/api/auth/verify-email")
@limiter.limit("10/minute")
async def verify_email(request: Request, verification: EmailVerification):
    print(f"🔍 DEBUG: Verifying email {verification.email} with code {verification.code}")
    
    # Try database first, then memory
    stored_data = None
    stored_code = None
    expires_at = None
    user_data = None
    is_from_database = False
    
    try:
        # Try to get verification data from DATABASE
        query = verification_codes.select().where(verification_codes.c.email == verification.email)
        db_data = await database.fetch_one(query)
        
        if db_data:
            stored_data = db_data
            stored_code = db_data.code
            expires_at = db_data.expires_at
            user_data = db_data.user_data
            is_from_database = True
            print("🔍 DEBUG: Found verification code in database")
        else:
            print("🔍 DEBUG: No verification code found in database, checking memory...")
            
    except Exception as e:
        print(f"⚠️ Database lookup failed: {str(e)}")
    
    # Fallback to memory storage if database lookup failed or no data found
    if not stored_data and verification.email in VERIFICATION_CODES:
        memory_data = VERIFICATION_CODES[verification.email]
        stored_code = memory_data["code"]
        expires_at = memory_data["expires"]
        user_data = memory_data["user_data"]
        is_from_database = False
        print("🔍 DEBUG: Found verification code in memory")
    
    if not stored_code:
        print(f"❌ DEBUG: Email {verification.email} not found in verification codes")
        # Show available emails for debugging
        try:
            all_codes = await database.fetch_all(verification_codes.select())
            available_emails = [row.email for row in all_codes]
            print(f"🔍 DEBUG: Available emails in DB: {available_emails}")
        except:
            pass
        memory_emails = list(VERIFICATION_CODES.keys())
        print(f"🔍 DEBUG: Available emails in memory: {memory_emails}")
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
    
    print(f"🔍 DEBUG: Stored code: {stored_code}, Received code: {verification.code}")
    print(f"🔍 DEBUG: Codes match: {stored_code == verification.code}")
    print(f"🔍 DEBUG: Code expires at: {expires_at}")
    
    # Check if code matches
    if stored_code != verification.code:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    
    # Handle timezone comparison properly - normalize everything to UTC
    from datetime import timezone
    current_time = datetime.now(timezone.utc)
    
    # Convert expires_at to UTC if it has timezone info, otherwise assume UTC
    if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is not None:
        # Already has timezone info
        expires_utc = expires_at
    else:
        # Assume it's UTC and add timezone info
        expires_utc = expires_at.replace(tzinfo=timezone.utc) if expires_at else None
    
    print(f"🔍 DEBUG: Current time (UTC): {current_time}")
    print(f"🔍 DEBUG: Expires at (UTC): {expires_utc}")
    
    if expires_utc and expires_utc < current_time:
        # Delete expired code from both storage locations
        if is_from_database:
            try:
                await database.execute(
                    verification_codes.delete().where(verification_codes.c.email == verification.email)
                )
            except:
                pass
        if verification.email in VERIFICATION_CODES:
            del VERIFICATION_CODES[verification.email]
        
        raise HTTPException(status_code=400, detail="Verification code has expired")
    
    # Create user in database
    # Handle case where user_data might be JSON string instead of dict (deployment issue)
    if isinstance(user_data, str):
        import json
        user_data = json.loads(user_data)
    
    user_data["verified"] = True
    user_data["email_verified_at"] = current_time.replace(tzinfo=None)  # Store as naive datetime
    
    await create_user(user_data)
    
    # Delete verification code from both locations
    if is_from_database:
        try:
            await database.execute(
                verification_codes.delete().where(verification_codes.c.email == verification.email)
            )
        except:
            pass
    
    if verification.email in VERIFICATION_CODES:
        del VERIFICATION_CODES[verification.email]
    
    # Create welcome notification
    await database.execute(
        notifications.insert().values(
            id=str(uuid.uuid4()),
            user_id=user_data["id"],
            type="info",
            title="Welcome to AfyaMetrix!",
            message="Your account has been successfully verified. Start reporting health data in your community.",
            read=False
        )
    )
    
    print(f"✅ DEBUG: Successfully verified and created user: {user_data['email']}")
    return {"message": "Email verified successfully"}

@app.post("/api/auth/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login_user(request: Request, user_credentials: UserLogin):
    user = await get_user_by_email(user_credentials.email)
    
    if not user or not verify_password(user_credentials.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.verified:
        raise HTTPException(status_code=401, detail="Please verify your email before logging in")
    
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id)}
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            name=user.name,
            email=user.email,
            role=user.role,
            location=user.location,
            verified=user.verified
        )
    )

@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user=Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        location=current_user.location,
        verified=current_user.verified
    )

@app.post("/api/auth/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, forgot_data: ForgotPassword, background_tasks: BackgroundTasks):
    """
    Send password reset code to user's email.
    """
    cleanup_expired_codes()
    
    user = await get_user_by_email(forgot_data.email)
    if not user:
        # Security: Don't reveal if email exists or not
        return {"message": "If the email exists, a reset code has been sent"}
    
    # Generate reset code
    reset_code = generate_verification_code()
    
    # Store reset code (expires in 15 minutes)
    PASSWORD_RESET_CODES[forgot_data.email] = {
        "code": reset_code,
        "expires": datetime.utcnow() + timedelta(minutes=15),
        "user_id": str(user.id)
    }
    
    # Send reset email
    background_tasks.add_task(
        email_service.send_password_reset_email,
        forgot_data.email,
        reset_code,
        user.name
    )
    
    return {"message": "If the email exists, a reset code has been sent"}

@app.post("/api/auth/reset-password")
@limiter.limit("5/minute")
async def reset_password(request: Request, reset_data: ResetPassword):
    """
    Reset user password with verification code.
    """
    cleanup_expired_codes()
    
    if reset_data.email not in PASSWORD_RESET_CODES:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
    
    stored_data = PASSWORD_RESET_CODES[reset_data.email]
    
    if stored_data["code"] != reset_data.code:
        raise HTTPException(status_code=400, detail="Invalid reset code")
    
    if stored_data["expires"] < datetime.utcnow():
        del PASSWORD_RESET_CODES[reset_data.email]
        raise HTTPException(status_code=400, detail="Reset code has expired")
    
    # Update user password
    new_password_hash = get_password_hash(reset_data.new_password)
    await update_user(stored_data["user_id"], {"password": new_password_hash})
    
    # Remove reset code
    del PASSWORD_RESET_CODES[reset_data.email]
    
    return {"message": "Password reset successfully"}

@app.post("/api/auth/resend-verification")
@limiter.limit("3/minute") 
async def resend_verification(request: Request, resend_data: ResendVerification, background_tasks: BackgroundTasks):
    """
    Resend verification code to user's email.
    """
    cleanup_expired_codes()
    
    # Check if user already exists (and verified)
    existing_user = await get_user_by_email(resend_data.email)
    if existing_user and existing_user.verified:
        raise HTTPException(status_code=400, detail="Email is already verified")
    
    # Check if there's a pending verification in database or memory
    pending_verification = None
    
    try:
        # Check database first
        query = verification_codes.select().where(verification_codes.c.email == resend_data.email)
        db_data = await database.fetch_one(query)
        if db_data:
            pending_verification = db_data.user_data
    except Exception as e:
        print(f"⚠️ Database lookup error: {str(e)}")
    
    # Check memory if not found in database
    if not pending_verification and resend_data.email in VERIFICATION_CODES:
        pending_verification = VERIFICATION_CODES[resend_data.email]["user_data"]
    
    if not pending_verification:
        raise HTTPException(status_code=400, detail="No pending verification found for this email")
    
    # Generate new verification code
    new_verification_code = generate_verification_code()
    
    # Clean up existing codes first
    try:
        await database.execute(
            verification_codes.delete().where(verification_codes.c.email == resend_data.email)
        )
    except:
        pass
    
    if resend_data.email in VERIFICATION_CODES:
        del VERIFICATION_CODES[resend_data.email]
    
    # Store new verification code
    try:
        from datetime import timezone
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        
        await database.execute(
            verification_codes.insert().values(
                email=resend_data.email,
                code=new_verification_code,
                expires_at=expires_at,
                user_data=pending_verification
            )
        )
        
        # Also store in memory as backup
        VERIFICATION_CODES[resend_data.email] = {
            "code": new_verification_code,
            "expires": expires_at.replace(tzinfo=None),
            "user_data": pending_verification
        }
        
    except Exception as e:
        # Fallback to memory only
        VERIFICATION_CODES[resend_data.email] = {
            "code": new_verification_code,
            "expires": datetime.utcnow() + timedelta(minutes=15),
            "user_data": pending_verification
        }
        print(f"⚠️ Using memory storage only: {str(e)}")
    
    # Send new verification email
    background_tasks.add_task(
        email_service.send_verification_email,
        resend_data.email,
        new_verification_code,
        pending_verification["name"]
    )
    
    print(f"🔑 DEBUG: New verification code for {resend_data.email}: {new_verification_code}")
    
    return {"message": "Verification code resent successfully"}

# ========================================
# USER PROFILE ENDPOINTS
# ========================================

@app.patch("/api/user/profile")
@limiter.limit("30/minute")
async def update_profile(request: Request, profile_update: UserProfileUpdate, current_user=Depends(get_current_user)):
    update_data = {}
    if profile_update.name:
        update_data["name"] = profile_update.name
    if profile_update.location:
        update_data["location"] = profile_update.location
    
    if update_data:
        await update_user(str(current_user.id), update_data)
    
    return {"message": "Profile updated successfully"}

@app.post("/api/user/change-password")
@limiter.limit("5/minute")
async def change_password(request: Request, password_change: PasswordChange, current_user=Depends(get_current_user)):
    if not verify_password(password_change.current_password, current_user.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    new_password_hash = get_password_hash(password_change.new_password)
    await update_user(str(current_user.id), {"password": new_password_hash})
    
    return {"message": "Password changed successfully"}

@app.get("/api/user/notification-settings")
async def get_notification_settings(current_user=Depends(get_current_user)):
    settings = current_user.notification_settings or {
        "emailNotifications": True,
        "smsAlerts": False,
        "systemNotifications": True
    }
    return settings

@app.put("/api/user/notification-settings")
@limiter.limit("30/minute")
async def update_notification_settings(
    request: Request, 
    settings: NotificationSettings, 
    current_user=Depends(get_current_user)
):
    await update_user(str(current_user.id), {
        "notification_settings": settings.dict()
    })
    return {"message": "Settings updated successfully"}

# ========================================
# NOTIFICATIONS ENDPOINTS
# ========================================

@app.get("/api/notifications")
async def get_notifications(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user)
):
    query = (
        notifications.select()
        .where(notifications.c.user_id == current_user.id)
        .order_by(notifications.c.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    
    result = await database.fetch_all(query)
    
    return {
        "notifications": [
            {
                "id": str(row.id),
                "type": row.type,
                "title": row.title,
                "message": row.message,
                "timestamp": row.created_at.isoformat(),
                "read": row.read
            }
            for row in result
        ]
    }

@app.patch("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user=Depends(get_current_user)):
    query = (
        notifications.update()
        .where(notifications.c.id == notification_id)
        .where(notifications.c.user_id == current_user.id)
        .values(read=True)
    )
    
    result = await database.execute(query)
    if result == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"message": "Marked as read"}

@app.delete("/api/notifications/{notification_id}")
async def delete_notification(notification_id: str, current_user=Depends(get_current_user)):
    query = (
        notifications.delete()
        .where(notifications.c.id == notification_id)
        .where(notifications.c.user_id == current_user.id)
    )
    
    result = await database.execute(query)
    if result == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"message": "Notification deleted"}

@app.patch("/api/notifications/mark-all-read")
async def mark_all_notifications_read(current_user=Depends(get_current_user)):
    query = (
        notifications.update()
        .where(notifications.c.user_id == current_user.id)
        .where(notifications.c.read == False)
        .values(read=True)
    )
    
    count = await database.execute(query)
    return {"message": "All notifications marked as read", "count": count}

# ========================================
# DASHBOARD ENDPOINTS
# ========================================

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user=Depends(get_current_user)):
    # Get user's cases for stats
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Today's cases
    today_query = (
        cases.select()
        .where(cases.c.user_id == current_user.id)
        .where(cases.c.created_at >= today)
    )
    today_cases = await database.fetch_all(today_query)
    today_count = sum(case.case_count for case in today_cases)
    
    # Week's cases
    week_query = (
        cases.select()
        .where(cases.c.user_id == current_user.id)
        .where(cases.c.created_at >= week_ago)
    )
    week_cases = await database.fetch_all(week_query)
    week_count = sum(case.case_count for case in week_cases)
    
    # Month's cases
    month_query = (
        cases.select()
        .where(cases.c.user_id == current_user.id)
        .where(cases.c.created_at >= month_ago)
    )
    month_cases = await database.fetch_all(month_query)
    month_count = sum(case.case_count for case in month_cases)
    
    # Pending reports
    pending_query = (
        cases.select()
        .where(cases.c.user_id == current_user.id)
        .where(cases.c.status == 'pending')
    )
    pending_cases = await database.fetch_all(pending_query)
    pending_count = len(pending_cases)
    
    return {
        "todayCases": today_count,
        "weekCases": week_count,
        "monthCases": month_count,
        "pendingReports": pending_count,
        "activeFacilities": 1,  # Static for demo
        "completionRate": 85.5,  # Static for demo
        "trend": {
            "value": 12.5,
            "direction": "up",
            "label": "vs last week"
        }
    }

@app.get("/api/dashboard/diseases")
async def get_disease_breakdown(current_user=Depends(get_current_user)):
    query = (
        cases.select()
        .where(cases.c.user_id == current_user.id)
    )
    
    user_cases = await database.fetch_all(query)
    
    # Count cases by disease type
    disease_counts = {}
    for case in user_cases:
        disease = case.disease_type
        disease_counts[disease] = disease_counts.get(disease, 0) + case.case_count
    
    return [
        {"name": disease, "count": count}
        for disease, count in disease_counts.items()
    ]

@app.get("/api/dashboard/recent")
async def get_recent_cases(
    limit: int = Query(10, ge=1, le=50),
    current_user=Depends(get_current_user)
):
    query = (
        cases.select()
        .where(cases.c.user_id == current_user.id)
        .order_by(cases.c.created_at.desc())
        .limit(limit)
    )
    
    recent_cases = await database.fetch_all(query)
    
    return [
        {
            "id": str(case.id),
            "diseaseType": case.disease_type,
            "cases": case.case_count,
            "date": case.created_at.strftime("%Y-%m-%d"),
            "worker": current_user.name,
            "status": case.status,
            "createdAt": case.created_at.isoformat(),
            "updatedAt": case.updated_at.isoformat()
        }
        for case in recent_cases
    ]

@app.get("/api/dashboard/alerts")
async def get_dashboard_alerts(current_user=Depends(get_current_user)):
    query = (
        dashboard_alerts.select()
        .where(dashboard_alerts.c.is_active == True)
        .order_by(dashboard_alerts.c.created_at.desc())
        .limit(20)
    )
    
    alerts = await database.fetch_all(query)
    
    return [
        {
            "id": str(alert.id),
            "type": alert.type,
            "title": alert.title,
            "message": alert.message,
            "location": alert.location,
            "timestamp": alert.created_at.isoformat(),
            "isRead": False  # Static for demo
        }
        for alert in alerts
    ]

# ========================================
# CASE MANAGEMENT ENDPOINTS
# ========================================

@app.get("/api/cases")
async def get_user_cases(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user)
):
    query = (
        cases.select()
        .where(cases.c.user_id == current_user.id)
        .order_by(cases.c.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    
    user_cases = await database.fetch_all(query)
    
    return [
        {
            "id": str(case.id),
            "diseaseType": case.disease_type,
            "cases": case.case_count,
            "date": case.created_at.strftime("%Y-%m-%d"),
            "worker": current_user.name,
            "status": case.status,
            "caseDetails": case.case_details,
            "comments": case.comments,
            "photos": case.photos or [],
            "createdAt": case.created_at.isoformat(),
            "updatedAt": case.updated_at.isoformat()
        }
        for case in user_cases
    ]

@app.post("/api/cases", status_code=201)
@limiter.limit("60/minute")
async def create_case(request: Request, case_data: CaseCreate, current_user=Depends(get_current_user)):
    case_id = str(uuid.uuid4())
    
    query = cases.insert().values(
        id=case_id,
        user_id=current_user.id,
        disease_type=case_data.diseaseType,
        case_count=case_data.cases,
        case_details=case_data.caseDetails,
        comments=case_data.comments,
        photos=case_data.photos or [],
        status='pending'
    )
    
    await database.execute(query)
    
    return {
        "id": case_id,
        "message": "Case created successfully"
    }

@app.post("/api/dashboard/sync")
@limiter.limit("10/minute")
async def sync_offline_data(request: Request, sync_data: SyncRequest, current_user=Depends(get_current_user)):
    processed = 0
    
    for item in sync_data.items:
        try:
            case_id = str(uuid.uuid4())
            query = cases.insert().values(
                id=case_id,
                user_id=current_user.id,
                disease_type=item.get("diseaseType"),
                case_count=item.get("cases", 0),
                case_details=item.get("caseDetails"),
                status='synced'
            )
            await database.execute(query)
            processed += 1
        except Exception as e:
            print(f"Error syncing item: {e}")
    
    return {
        "message": "Sync completed",
        "processed": processed
    }

# ========================================
# HEALTH CHECK
# ========================================

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

# ========================================
# ROOT ENDPOINT
# ========================================

@app.get("/")
async def root():
    return {
        "message": "AfyaMetrix Production API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/api/docs"
    }

# ========================================
# HEALTH DATA ENDPOINTS (from main.py)
# ========================================

@app.get("/api/health-intelligence/risk-scores")
def get_health_risk_scores(
    country:  str  = Query(None, description="Filter by country name"),
    date:     str  = Query(None, description="Specific date YYYY-MM-DD"),
    min_risk: float = Query(0,   description="Minimum risk score (0-100)"),
    limit:    int  = Query(100,  description="Max records to return")
):
    """
    Returns health risk scores for all regions.
    
    This endpoint provides ML-generated disease risk intelligence.
    """
    df = HEALTH_DATA['regional_risk'].copy()
    
    if df.empty:
        raise HTTPException(status_code=503, detail="Health risk data not available")
    
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
    
    # Merge cluster labels if available
    if not HEALTH_DATA['clusters'].empty:
        df = df.merge(
            HEALTH_DATA['clusters'][[
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

@app.get("/api/health-intelligence/alerts")
def get_health_alerts(
    country:   str = Query(None, description="Filter by country"),
    min_score: float = Query(55, description="Minimum risk score for alerts"),
    limit:     int  = Query(50,  description="Max alerts to return")
):
    """
    Returns active health outbreak alerts.
    
    ML-powered early warning system for disease outbreaks.
    """
    df = HEALTH_DATA['regional_risk'].copy()
    
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
        "generated":  datetime.utcnow().isoformat(),
        "alerts":     alert_list
    }

@app.get("/api/health-intelligence/forecasts")
def get_health_forecasts(
    country: str = Query(None, description="Filter by country"),
    disease: str = Query(None, description="Filter by disease"),
    trend:   str = Query(None, description="Filter by trend: increasing/decreasing")
):
    """
    Returns 30-day disease forecasts using Prophet ML models.
    """
    df = HEALTH_DATA['forecasts'].copy()
    
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

@app.get("/api/health-intelligence/allocations")
def get_health_allocations(
    country:  str = Query(None, description="Filter by country"),
    resource: str = Query(None, description="Resource type: vaccines/ambulances/budget_usd etc")
):
    """
    Returns AI-recommended resource allocations per region.
    """
    df = HEALTH_DATA['allocations'].copy()
    
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

@app.get("/api/health-intelligence/narrative")
def get_health_narrative(
    country:  str = Query(..., description="Country name (required)"),
    region:   str = Query(..., description="Region name (required)"),
    language: str = Query("en", description="Language code: en/fr/sw")
):
    """
    Returns AI-generated health intelligence narrative for a region.
    
    Multilingual health summaries for non-technical health officials.
    """
    df = HEALTH_DATA['narratives'].copy()
    
    if df.empty:
        # Generate basic narrative from risk data
        risk_df = HEALTH_DATA['regional_risk']
        if risk_df.empty:
            raise HTTPException(status_code=503, detail="Health narrative data not available")
        
        latest = risk_df['date'].max()
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
    
    # Find matching region in narratives
    match = df[
        (df['country'].str.lower() == country.lower()) &
        (df['region'].str.lower() == region.lower())
    ]
    
    if len(match) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Narrative for '{region}' in '{country}' not found"
        )
    
    row      = match.iloc[0]
    lang_col = f'narrative_{language}' if f'narrative_{language}' in row.index else 'narrative_en'
    
    return {
        "country":   country,
        "region":    region,
        "language":  language,
        "risk_score": float(row.get('risk_score', 0)),
        "narrative":  row.get(lang_col, row.get('narrative_en', 'No narrative available'))
    }

@app.get("/api/health-intelligence/cross-border-alerts")
def get_cross_border_health_alerts(
    country: str = Query(None, description="Filter by source OR target country"),
    disease: str = Query(None, description="Filter by disease")
):
    """
    Returns active cross-border disease spread alerts.
    
    Early warning system for cross-border epidemic spread.
    """
    df = HEALTH_DATA['cross_border'].copy()
    
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

@app.get("/api/health-intelligence/clusters")
def get_health_clusters(
    cluster: str = Query(None, description="Filter by cluster label")
):
    """
    Returns ML-based region cluster classifications and intervention plans.
    """
    df = HEALTH_DATA['clusters'].copy()
    
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

@app.get("/api/health-intelligence/voice-query")
def health_voice_query(q: str = Query(..., description="Voice query text")):
    """
    Processes natural language voice queries for health data.
    
    AI-powered voice assistant for health intelligence queries.
    """
    query     = q.lower().strip()
    risk_df   = HEALTH_DATA['regional_risk']
    
    if risk_df.empty:
        return {
            "intent": "no_data",
            "response": "Health data is not available at the moment.",
            "data": []
        }
    
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
        alerts_df = HEALTH_DATA['cross_border']
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
                f"AfyaMetrix health intelligence update: "
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

@app.get("/api/health-intelligence/dashboard-summary")
def get_health_dashboard_summary(
    country: str = Query(None, description="Filter by country")
):
    """
    Returns complete health intelligence summary for dashboards.
    
    Comprehensive health data overview for executive dashboards.
    """
    risk_df  = HEALTH_DATA['regional_risk']
    
    if risk_df.empty:
        return {
            "error": "Health data not available",
            "message": "Please ensure health data is loaded"
        }
    
    latest   = risk_df['date'].max()
    snap     = risk_df[risk_df['date'] == latest]
    
    if country:
        snap = snap[snap['country'].str.lower() == country.lower()]
    
    cross = HEALTH_DATA['cross_border']
    
    return {
        "generated":          datetime.utcnow().isoformat(),
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