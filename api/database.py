# ========================================
# AfyaMetrix Database Configuration
# File: api/database.py
# ========================================

import os
from databases import Database
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, ENUM, JSONB # Changed JSON to JSONB
from sqlalchemy.sql import func
import uuid
from datetime import datetime, timezone # Added timezone
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:password@localhost:5432/afyametrix"
)

# ========================================
# DATABASE INSTANCE (THE FIX)
# ========================================
# We pass statement_cache_size=0 directly to the Database constructor.
# The 'databases' library ignores this setting if it's placed in the URL string.
database = Database(
    DATABASE_URL, 
    force_rollback=False, 
    min_size=2, 
    max_size=15, # Increased for production concurrency
    statement_cache_size=0 # <--- THIS FIXES THE PGBOUNCER ERROR
)

metadata = MetaData()

# ========================================
# TABLE DEFINITIONS
# ========================================

# Users table
users = Table(
    "users",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("name", String(100), nullable=False),
    Column("email", String(255), unique=True, nullable=False, index=True),
    Column("password", String(255), nullable=False), # MUST BE HASHED (e.g., bcrypt) in app logic!
    Column("role", String(50), nullable=False),
    Column("location", String(255), nullable=True),
    Column("verified", Boolean, default=False),
    Column("notification_settings", JSONB, default=lambda: {
        "emailNotifications": True,
        "smsAlerts": False,
        "systemNotifications": True
    }),
    Column("email_verified_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
)

# Notifications table
notification_type = ENUM('info', 'warning', 'error', name='notification_type')
notifications = Table(
    "notifications",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
    Column("type", notification_type, nullable=False),
    Column("title", String(255), nullable=False),
    Column("message", Text, nullable=False),
    Column("read", Boolean, default=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

# Cases table
case_status = ENUM('pending', 'synced', name='case_status')
cases = Table(
    "cases",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
    Column("disease_type", String(100), nullable=False),
    Column("case_count", Integer, nullable=False),
    Column("case_details", Text, nullable=True),
    Column("comments", Text, nullable=True),
    Column("photos", JSONB, default=list),  # Changed to JSONB for better Postgres performance
    Column("status", case_status, default='pending'),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
)

# Verification codes table
verification_codes = Table(
    "verification_codes",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("email", String(255), nullable=False, index=True),
    Column("code", String(6), nullable=False),  # Matches Supabase schema: VARCHAR(6)
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("user_data", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

# Dashboard alerts table
alert_type = ENUM('warning', 'info', 'error', name='alert_type')
dashboard_alerts = Table(
    "dashboard_alerts",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("type", alert_type, nullable=False),
    Column("title", String(255), nullable=False),
    Column("message", Text, nullable=False),
    Column("location", String(255), nullable=True),
    Column("is_active", Boolean, default=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

# ========================================
# DATABASE UTILITIES
# ========================================

async def connect_db():
    """Connect to database"""
    await database.connect()
    print("✅ Database connected")

async def disconnect_db():
    """Disconnect from database"""
    await database.disconnect()
    print("📴 Database disconnected")

def create_tables(engine=None):
    """Create all tables (Note: Use Alembic for production schema migrations)"""
    if engine is None:
        engine = create_engine(DATABASE_URL)
    metadata.create_all(engine)
    print("✅ Database tables created")

async def get_user_by_email(email: str):
    """Get user by email"""
    query = users.select().where(users.c.email == email)
    return await database.fetch_one(query)

async def get_user_by_id(user_id: str):
    """Get user by ID"""
    query = users.select().where(users.c.id == user_id)
    return await database.fetch_one(query)

async def create_user(user_data: dict):
    """Create new user (Ensure password is hashed before calling this!)"""
    query = users.insert().values(**user_data)
    return await database.execute(query)

async def update_user(user_id: str, update_data: dict):
    """Update user"""
    # FIX: Use timezone-aware UTC time instead of deprecated utcnow()
    update_data["updated_at"] = datetime.now(timezone.utc)
    query = users.update().where(users.c.id == user_id).values(**update_data)
    return await database.execute(query)                          

# # AfyaMetrix Database Configuration
# # File: api/database.py
# # ========================================

# import os
# from databases import Database
# from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Boolean, DateTime, Text, JSON
# from sqlalchemy.dialects.postgresql import UUID, ENUM
# from sqlalchemy.sql import func
# import uuid
# from datetime import datetime
# from dotenv import load_dotenv

# load_dotenv()

# # Database configuration
# DATABASE_URL = os.getenv(
#     "DATABASE_URL", 
#     "postgresql://postgres:password@localhost:5432/afyametrix"
# )

# # Fix for Supabase pgbouncer - disable prepared statements
# if "supabase" in DATABASE_URL:
#     if "?" in DATABASE_URL:
#         DATABASE_URL += "&prepared_statement_cache_size=0"
#     else:
#         DATABASE_URL += "?prepared_statement_cache_size=0"

# # Database instance
# database = Database(DATABASE_URL, force_rollback=False, min_size=1, max_size=3)
# metadata = MetaData()

# # ========================================
# # TABLE DEFINITIONS
# # ========================================

# # Users table (extends existing auth table)
# users = Table(
#     "users",
#     metadata,
#     Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
#     Column("name", String(100), nullable=False),
#     Column("email", String(255), unique=True, nullable=False, index=True),
#     Column("password", String(255), nullable=False),
#     Column("role", String(50), nullable=False),
#     Column("location", String(255), nullable=True),
#     Column("verified", Boolean, default=False),
#     Column("notification_settings", JSON, default=lambda: {
#         "emailNotifications": True,
#         "smsAlerts": False,
#         "systemNotifications": True
#     }),
#     Column("email_verified_at", DateTime(timezone=True), nullable=True),
#     Column("created_at", DateTime(timezone=True), server_default=func.now()),
#     Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
# )

# # Notifications table
# notification_type = ENUM('info', 'warning', 'error', name='notification_type')
# notifications = Table(
#     "notifications",
#     metadata,
#     Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
#     Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
#     Column("type", notification_type, nullable=False),
#     Column("title", String(255), nullable=False),
#     Column("message", Text, nullable=False),
#     Column("read", Boolean, default=False),
#     Column("created_at", DateTime(timezone=True), server_default=func.now()),
# )

# # Cases table
# case_status = ENUM('pending', 'synced', name='case_status')
# cases = Table(
#     "cases",
#     metadata,
#     Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
#     Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
#     Column("disease_type", String(100), nullable=False),
#     Column("case_count", Integer, nullable=False),
#     Column("case_details", Text, nullable=True),
#     Column("comments", Text, nullable=True),
#     Column("photos", JSON, default=list),  # Array of photo URLs
#     Column("status", case_status, default='pending'),
#     Column("created_at", DateTime(timezone=True), server_default=func.now()),
#     Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
# )

# # Create verification_codes table for production
# verification_codes = Table(
#     "verification_codes",
#     metadata,
#     Column("email", String(255), primary_key=True),
#     Column("code", String(6), nullable=False),
#     Column("expires_at", DateTime(timezone=True), nullable=False),
#     Column("user_data", JSON, nullable=False),
#     Column("created_at", DateTime(timezone=True), server_default=func.now()),
# )
# # Dashboard alerts table
# alert_type = ENUM('warning', 'info', 'error', name='alert_type')
# dashboard_alerts = Table(
#     "dashboard_alerts",
#     metadata,
#     Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
#     Column("type", alert_type, nullable=False),
#     Column("title", String(255), nullable=False),
#     Column("message", Text, nullable=False),
#     Column("location", String(255), nullable=True),
#     Column("is_active", Boolean, default=True),
#     Column("created_at", DateTime(timezone=True), server_default=func.now()),
# )

# # ========================================
# # DATABASE UTILITIES
# # ========================================

# async def connect_db():
#     """Connect to database"""
#     await database.connect()
#     print("✅ Database connected")

# async def disconnect_db():
#     """Disconnect from database"""
#     await database.disconnect()
#     print("📴 Database disconnected")

# def create_tables(engine=None):
#     """Create all tables"""
#     if engine is None:
#         engine = create_engine(DATABASE_URL)
#     metadata.create_all(engine)
#     print("✅ Database tables created")

# async def get_user_by_email(email: str):
#     """Get user by email"""
#     query = users.select().where(users.c.email == email)
#     return await database.fetch_one(query)

# async def get_user_by_id(user_id: str):
#     """Get user by ID"""
#     query = users.select().where(users.c.id == user_id)
#     return await database.fetch_one(query)

# async def create_user(user_data: dict):
#     """Create new user"""
#     query = users.insert().values(**user_data)
#     return await database.execute(query)

# async def update_user(user_id: str, update_data: dict):
#     """Update user"""
#     update_data["updated_at"] = datetime.utcnow()
#     query = users.update().where(users.c.id == user_id).values(**update_data)
#     return await database.execute(query)