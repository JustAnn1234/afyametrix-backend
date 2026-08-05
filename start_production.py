#!/usr/bin/env python3
"""
Production startup script for AfyaMetrix backend.
This script handles database migrations and starts the production server.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_database_connection():
    """Check if database is accessible."""
    try:
        from api.database import database
        await database.connect()
        logger.info("✅ Database connection successful")
        await database.disconnect()
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False

def check_environment_variables():
    """Validate critical environment variables."""
    required_vars = [
        "JWT_SECRET_KEY",
        "PASSWORD_SALT", 
        "DATABASE_URL",
        "RESEND_API_KEY"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Missing required environment variables: {missing_vars}")
        return False
    
    logger.info("✅ All required environment variables present")
    return True

def run_migrations():
    """Run database migrations."""
    try:
        # Import here to avoid circular imports
        from api.create_tables import create_tables
        asyncio.run(create_tables())
        logger.info("✅ Database tables created/updated")
        return True
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

async def main():
    """Main startup sequence."""
    logger.info(f"🚀 Starting AfyaMetrix Production Server at {datetime.now()}")
    
    # 1. Check environment variables
    if not check_environment_variables():
        sys.exit(1)
    
    # 2. Check database connection
    if not await check_database_connection():
        sys.exit(1)
    
    # 3. Run migrations
    if not run_migrations():
        sys.exit(1)
    
    logger.info("✅ Production startup checks completed successfully")
    logger.info("🌟 AfyaMetrix backend ready for production traffic")

if __name__ == "__main__":
    asyncio.run(main())