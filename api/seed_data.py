# ========================================
# AfyaMetrix Sample Data Seeder
# File: api/seed_data.py
# ========================================

import asyncio
import uuid
from datetime import datetime, timedelta
from database import database, connect_db, disconnect_db, dashboard_alerts
import random

# Sample alerts data
SAMPLE_ALERTS = [
    {
        "type": "warning",
        "title": "Malaria Outbreak Alert",
        "message": "Increased malaria cases reported in Kibera region. Immediate attention required.",
        "location": "Kibera, Kenya"
    },
    {
        "type": "info",
        "title": "Vaccination Campaign",
        "message": "COVID-19 vaccination campaign starting next week in all health centers.",
        "location": "Lagos, Nigeria"
    },
    {
        "type": "error",
        "title": "Critical Medicine Shortage",
        "message": "Severe shortage of antimalarial drugs reported. Emergency supply needed.",
        "location": "Addis Ababa, Ethiopia"
    },
    {
        "type": "warning",
        "title": "Cholera Risk Alert",
        "message": "Water contamination detected. Increased cholera risk in the area.",
        "location": "Kampala, Uganda"
    },
    {
        "type": "info",
        "title": "Health Training Session",
        "message": "Community health worker training session scheduled for next month.",
        "location": "Dar es Salaam, Tanzania"
    }
]

async def seed_sample_data():
    """Add sample dashboard alerts"""
    try:
        await connect_db()
        
        print("🌱 Seeding sample dashboard alerts...")
        
        for alert_data in SAMPLE_ALERTS:
            query = dashboard_alerts.insert().values(
                id=str(uuid.uuid4()),
                type=alert_data["type"],
                title=alert_data["title"],
                message=alert_data["message"],
                location=alert_data["location"],
                is_active=True,
                created_at=datetime.utcnow() - timedelta(
                    days=random.randint(0, 7),
                    hours=random.randint(0, 23)
                )
            )
            await database.execute(query)
        
        print("✅ Sample data seeded successfully!")
        
        await disconnect_db()
        
    except Exception as e:
        print(f"❌ Error seeding data: {e}")

if __name__ == "__main__":
    asyncio.run(seed_sample_data())