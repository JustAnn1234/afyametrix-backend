# ========================================
# AfyaMetrix Database Setup
# File: api/create_tables.py
# ========================================

import asyncio
from sqlalchemy import create_engine
from database import metadata, DATABASE_URL, database
import os

async def create_all_tables():
    """Create all database tables"""
    try:
        # Create engine
        engine = create_engine(DATABASE_URL)
        
        # Create all tables
        metadata.create_all(engine)
        print("✅ All database tables created successfully!")
        
        # Connect to database to test
        await database.connect()
        print("✅ Database connection successful!")
        await database.disconnect()
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure PostgreSQL is running")
        print("2. Check DATABASE_URL in .env file")
        print("3. Ensure database 'afyametrix' exists")
        print("4. Verify connection credentials")

if __name__ == "__main__":
    print("🚀 Creating AfyaMetrix database tables...")
    asyncio.run(create_all_tables())