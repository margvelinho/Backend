from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
from flask_cors import CORS
import sqlite3
import re
import os
from pathlib import Path
 
# Define absolute path to database
DB_PATH = Path("db/users.db")
print(f"Using database at: {DB_PATH}")
 
# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
 
# Initialize Swagger API
api = Api(
    app,
    version='1.0',
    title='User Registration API',
    description='A simple API for user registration and phone number storage',
    doc='/swagger/'
)
 
# Define namespaces
users_ns = api.namespace('users', description='User operations')
numbers_ns = api.namespace('numbers', description='Phone number operations')
 
# Database initialization
def init_db():
    try:
        # Create parent directory if it doesn't exist
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                company TEXT,
                email TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK (email IS NOT NULL OR phone IS NOT NULL)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS users_numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                details_number TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()
 
init_db()
 
# Validation functions
def validate_email(email):
    pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    return re.match(pattern, email) is not None
 
def validate_phone(phone):
    cleaned_phone = re.sub(r'[\s\-\(\)\+]', '', phone)
    return cleaned_phone.isdigit() and len(cleaned_phone) >= 7
 
# API Models
user_model = api.model('User', {
    'name': fields.String(required=True),
    'company': fields.String(),
    'email': fields.String(),
    'phone': fields.String()
})
 
number_model = api.model('PhoneNumber', {
    'details_number': fields.String(required=True)
})
 
# User Registration Endpoint
@users_ns.route('/register')
class UserRegistration(Resource):
    @users_ns.expect(user_model)
    @users_ns.response(201, 'Success')
    @users_ns.response(400, 'Validation Error')
    def post(self):
        """Register a new user"""
        conn = None
        try:
            data = request.get_json()
            print(f"Received registration data: {data}")
            if not data:
                return {'error': 'No data provided'}, 400
            name = data.get('name', '').strip()
            company = data.get('company', '').strip() or None
            email = data.get('email', '').strip() or None
            phone = data.get('phone', '').strip() or None
 
            # Validation
            if not name:
                return {'error': 'Name is required'}, 400
            if not email and not phone:
                return {'error': 'Either email or phone number is required'}, 400
            if email and not validate_email(email):
                return {'error': 'Invalid email format'}, 400
            if phone and not validate_phone(phone):
                return {'error': 'Invalid phone number format'}, 400
 
            # Database operation
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, phone, company) VALUES (?, ?, ?, ?)",
                (name, email, phone, company)
            )
            user_id = cursor.lastrowid
            conn.commit()
            print(f"Successfully registered user with ID: {user_id}")
            # Verify insertion
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            print(f"Verification: {cursor.fetchone()}")
            return {
                'message': 'Registration successful!',
                'user_id': user_id
            }, 201
        except sqlite3.IntegrityError as e:
            print(f"Database integrity error: {e}")
            return {'error': 'Database error occurred'}, 500
        except Exception as e:
            print(f"Unexpected error: {e}")
            return {'error': 'An unexpected error occurred'}, 500
        finally:
            if conn:
                conn.close()
 
# Phone Number Endpoint
@numbers_ns.route('/detail_number')
class PhoneNumber(Resource):
    @numbers_ns.expect(number_model)
    @numbers_ns.response(201, 'Success')
    @numbers_ns.response(400, 'Validation Error')
    def post(self):
        """Store a phone number"""
        conn = None
        try:
            data = request.get_json()
            print(f"Received phone number data: {data}")
            if not data:
                return {'error': 'No data provided'}, 400
            details_number = data.get('details_number', '').strip()
            if not details_number:
                return {'error': 'Details number is required'}, 400
            if not validate_phone(details_number):
                return {'error': 'Invalid phone number format'}, 400
 
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users_numbers (details_number) VALUES (?)",
                (details_number,)
            )
            number_id = cursor.lastrowid
            conn.commit()
            print(f"Successfully stored phone number with ID: {number_id}")
            return {
                'message': 'Phone number saved successfully!',
                'number_id': number_id
            }, 201
        except Exception as e:
            print(f"Error saving phone number: {e}")
            return {'error': 'An unexpected error occurred'}, 500
        finally:
            if conn:
                conn.close()
 
# Diagnostic Endpoints
@users_ns.route('/all')
class GetAllUsers(Resource):
    def get(self):
        """Get all users"""
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
            # Convert to list of dictionaries for better JSON structure
            columns = [description[0] for description in cursor.description]
            users = [dict(zip(columns, row)) for row in rows]
            return users  # ✅ Return the data directly, no jsonify()
        except Exception as e:
            return {'error': str(e)}, 500
        finally:
            if conn:
                conn.close()
 
@users_ns.route('/delete_all')
class DeleteAllUsers(Resource):
    def delete(self):
        """Delete all users (for testing)"""
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users")
            conn.commit()
            return {'message': 'All users deleted successfully!'}, 200
        except Exception as e:
            return {'error': str(e)}, 500
        finally:
            if conn:
                conn.close()
 
# Health Check
@api.route('/health')
class HealthCheck(Resource):
    def get(self):
        """Check API status"""
        return {
            'status': 'OK',
            'database': {
                'path': str(DB_PATH),
                'exists': os.path.exists(DB_PATH),
                'size': os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
            }
        }, 200
 
@numbers_ns.route('/all')
class GetAllNumbers(Resource):
    def get(self):
        """Get all phone numbers"""
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users_numbers")
            rows = cursor.fetchall()
            # Convert to list of dictionaries for better JSON structure
            columns = [description[0] for description in cursor.description]
            numbers = [dict(zip(columns, row)) for row in rows]
            return numbers  # ✅ Return the data directly, no jsonify()
        except Exception as e:
            return {'error': str(e)}, 500
        finally:
            if conn:
                conn.close()
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
