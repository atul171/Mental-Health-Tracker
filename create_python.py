from pymongo import MongoClient
from werkzeug.security import generate_password_hash
import certifi
from dotenv import load_dotenv
import os
import datetime

load_dotenv()

client = MongoClient(
    os.getenv('MONGO_URI'),
    tlsCAFile=certifi.where()
)

db = client.mental_health_app

admin_email = "admin@gmail.com"
admin_password = "Admin123"

if db.users.find_one({'email': admin_email}):
    print("Admin already exists!")
else:
    db.users.insert_one({
        'email': admin_email,
        'password': generate_password_hash(admin_password),
        'is_admin': True,
        'first_name': 'Admin',
        'last_name': 'User',
        'created_at': datetime.datetime.now()
    })
    print("✅ Admin created successfully!")
    print(f"Email: {admin_email}")
    print(f"Password: {admin_password}")