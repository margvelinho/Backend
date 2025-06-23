from flask import Flask, request
from flask_restx import Api, Resource, fields
from flask_cors import CORS
import sqlite3
import re
import os
from pathlib import Path
from flask_jwt_extended import JWTManager, create_access_token, jwt_required

DB_PATH = Path(os.getenv("DB_PATH", "/tmp/users.db"))  
print(f"Using database at: {DB_PATH}")

app = Flask(__name__)

app.config['JWT_SECRET_KEY'] = 'ff3580a44a7721c28865eefe6f4613142c0ce47750bcebd1445328ba99e88c9b' 
jwt = JWTManager(app)

CORS(app) 

authorizations = {
    'Bearer Auth': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization',
        'description': 'Add "Bearer <JWT Token>"'
    }
}

api = Api(
    app,
    version='1.0',
    title='User Registration API',
    description='A simple API for user registration and phone number storage',
    doc='/swagger/',
    authorizations=authorizations,
    security='Bearer Auth'
)

users_ns = api.namespace('users', description='User operations')
numbers_ns = api.namespace('numbers', description='Phone number operations')
auth_ns = api.namespace('auth', description='Authentication')

test_user = {
    'name': 'Test1',
    'email': 'test1@example.com',
    'phone': 'test1num'
}

def init_db():
    """
    Initialize the database with proper error handling and Render.com compatibility
    """
    conn = None
    try:
        try:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            print(f"Database directory ready at: {DB_PATH.parent}")
        except Exception as dir_error:
            print(f"Warning: Could not create directory: {dir_error}")
            fallback_path = Path("instance/users.db")
            if fallback_path != DB_PATH:
                print(f"Trying fallback path: {fallback_path}")
                DB_PATH = fallback_path
                DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("PRAGMA foreign_keys = ON")

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
        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
        ''')

        conn.commit()
        print(f"Database initialized successfully at: {DB_PATH}")
        print(f"Database size: {os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0} bytes")

    except sqlite3.Error as db_error:
        print(f"SQLite error during initialization: {db_error}")
        if conn:
            conn.rollback()
        raise RuntimeError(f"Database initialization failed: {db_error}")

    except Exception as e:
        print(f"Unexpected error during DB initialization: {e}")
        raise RuntimeError(f"Database initialization failed: {e}")

    finally:
        if conn:
            try:
                conn.close()
            except Exception as close_error:
                print(f"Error closing connection: {close_error}")

init_db()


def validate_email(email):
    pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    cleaned_phone = re.sub(r'[\s\-\(\)\+]', '', phone)
    return cleaned_phone.isdigit() and len(cleaned_phone) >= 7

user_model = api.model('User', {
    'name': fields.String(required=True),
    'company': fields.String(),
    'email': fields.String(),
    'phone': fields.String()
})

number_model = api.model('PhoneNumber', {
    'details_number': fields.String(required=True)
})



@auth_ns.route('/login')
class Login(Resource):
    def post(self):
        data = request.get_json()
        if not data:
            print("Received empty or invalid JSON")
            return {'error': 'Missing JSON'}, 400

        username = data.get('name', '')
        email = data.get('email', '')
        phone = data.get('phone', '')

        print(f"Received login attempt: name={username}, email={email}, phone={phone}")

        if username == test_user['name'] and email == test_user['email'] and phone == test_user['phone']:
            access_token = create_access_token(identity=username)
            response = {'access_token': access_token}
            print(f"Login successful, returning response: {response}")
            return response, 200
        else:
            print("Invalid credentials")
            return {'error': 'Invalid credentials'}, 401


@numbers_ns.route('/detail_number')
class PhoneNumber(Resource):
    @jwt_required()
    @numbers_ns.expect(number_model)
    @numbers_ns.doc(security='Bearer Auth')
    def post(self):
        conn = None
        try:
            data = request.get_json()
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
            return {
                'message': 'Phone number saved successfully!',
                'number_id': number_id
            }, 201
        except Exception as e:
            return {'error': 'An unexpected error occurred'}, 500
        finally:
            if conn:
                conn.close()

@users_ns.route('/all')
class GetAllUsers(Resource):
    def get(self):
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            users = [dict(zip(columns, row)) for row in rows]
            return users
        except Exception as e:
            return {'error': str(e)}, 500
        finally:
            if conn:
                conn.close()

@users_ns.route('/delete_all')
class DeleteAllUsers(Resource):
    def delete(self):
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

@numbers_ns.route('/all')
class GetAllNumbers(Resource):
    def get(self):
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users_numbers")
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            numbers = [dict(zip(columns, row)) for row in rows]
            return numbers
        except Exception as e:
            return {'error': str(e)}, 500
        finally:
            if conn:
                conn.close()

@api.route('/health')
class HealthCheck(Resource):
    def get(self):
        return {
            'status': 'OK',
            'database': {
                'path': str(DB_PATH),
                'exists': os.path.exists(DB_PATH),
                'size': os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
            }
        }, 200

if __name__ == '__main__':
    print("Starting server...")
    print(f"Database path: {DB_PATH}")
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
