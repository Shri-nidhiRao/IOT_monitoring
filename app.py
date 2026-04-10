import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
import mysql.connector
from mysql.connector import Error

load_dotenv()

app = Flask(__name__)

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),  # No hardcoded fallbacks for security!
    'database': os.environ.get('DB_NAME', 'iot_monitoring'),
    'port': int(os.environ.get('DB_PORT', 3306))
}

def get_db_connection(include_db=True):
    try:
        config = DB_CONFIG.copy()
        if not include_db and 'database' in config:
            del config['database']
        conn = mysql.connector.connect(**config)
        return conn
    except Error as e:
        print(f"DB Error: {e}")
        return None

def init_db():
    """Initialize database and table if not exists."""
    conn = get_db_connection(include_db=False)
    if conn:
        cursor = conn.cursor()
        db_name = DB_CONFIG.get('database', 'iot_monitoring')
        try:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name};")
        except Error as e:
            print(f"Skipping DB creation (might be managed cloud DB): {e}")

        try:
            conn.database = db_name
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    temperature FLOAT NOT NULL,
                    pressure FLOAT NOT NULL,
                    status VARCHAR(10) NOT NULL,
                    limit_switch_A BOOLEAN NOT NULL,
                    limit_switch_B BOOLEAN NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            print("Database and table initialized.")
        except Error as e:
            print(f"Table creation error: {e}")
            
        cursor.close()
        conn.close()
    else:
        print("Failed to connect to DB for initialization.")

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/update', methods=['POST'])
def update_data():
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON payload provided'}), 400
            
        required_fields = ['temperature', 'pressure', 'status', 'limitA', 'limitB']
        for field in required_fields:
            if field not in data:
                return jsonify({'status': 'error', 'message': f'Missing required field: {field}'}), 400
                
        # Validate data types
        try:
            temp = float(data['temperature'])
            pres = float(data['pressure'])
            limitA = bool(data['limitA'])
            limitB = bool(data['limitB'])
            status_val = str(data['status'])
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid data types provided'}), 400

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            query = """
            INSERT INTO device_logs (temperature, pressure, status, limit_switch_A, limit_switch_B, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            # Optional timestamp
            timestamp = data.get('timestamp')
            if not timestamp:
                from datetime import datetime, timedelta
                # Force IST by adding 5 hours 30 mins to UTC. This ensures it displays 
                # correctly even when running on Render's UTC-default servers.
                ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
                timestamp = ist_time.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute(query, (temp, pres, status_val, limitA, limitB, timestamp))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/latest', methods=['GET'])
def latest_data():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM device_logs ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            if result.get('timestamp'):
                result['timestamp'] = result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            return jsonify(result)
    return jsonify({}), 404

@app.route('/history', methods=['GET'])
def history_data():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM device_logs ORDER BY id DESC LIMIT 50")
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        for r in results:
            if r.get('timestamp'):
                r['timestamp'] = r['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        return jsonify(results)
    return jsonify([]), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'db': 'available' if get_db_connection() else 'error'})

# Auto-initialize on import so gunicorn runs it.
try:
    init_db()
except Exception as e:
    print(f"Startup DB init failed: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
