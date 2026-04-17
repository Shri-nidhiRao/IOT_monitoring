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
    # First try connecting with the database (safe for cloud providers like Aiven)
    conn = get_db_connection(include_db=True)
    db_name = DB_CONFIG.get('database', 'iot_monitoring')
    
    if not conn:
        # Fallback for local hosting if database doesn't exist yet
        conn = get_db_connection(include_db=False)
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name};")
            except Error as e:
                print(f"Skipping DB creation (might be managed cloud DB): {e}")
            conn.database = db_name
            cursor.close()

    if conn:
        cursor = conn.cursor()
        try:
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
            
            # Safely alter table to add the required columns without dropping existing data
            try:
                cursor.execute("ALTER TABLE device_logs ADD COLUMN on_time TIME;")
            except Error:
                pass
            try:
                cursor.execute("ALTER TABLE device_logs ADD COLUMN off_time TIME;")
            except Error:
                pass
            try:
                cursor.execute("ALTER TABLE device_logs ADD COLUMN device_id VARCHAR(50);")
            except Error:
                pass
            try:
                cursor.execute("ALTER TABLE device_logs ADD COLUMN device_name VARCHAR(100);")
            except Error:
                pass
            
            # Create scheduling tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedule_settings (
                    id INT PRIMARY KEY,
                    on_time TIME,
                    off_time TIME
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedule_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    on_time TIME,
                    off_time TIME,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Seed default schedule if empty
            cursor.execute("SELECT COUNT(*) FROM schedule_settings WHERE id = 1")
            (count,) = cursor.fetchone()
            if count == 0:
                cursor.execute("INSERT INTO schedule_settings (id, on_time, off_time) VALUES (1, '08:00:00', '18:00:00')")

            conn.commit()
            print("Database and tables initialized.")
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
            
        required_fields = ['mainid', 'temperature', 'pressure', 'limitA', 'limitB']
        for field in required_fields:
            if field not in data:
                return jsonify({'status': 'error', 'message': f'Missing required field: {field}'}), 400
                
        # Validate data types
        try:
            device_id = str(data['mainid'])
            device_name = str(data.get('Device_name', data.get('device_name', 'Unknown')))
            temp = float(data['temperature'])
            pres = float(data['pressure'])
            limitA = bool(data['limitA'])
            limitB = bool(data['limitB'])
            status_val = str(data.get('status', 'N/A'))
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid data types provided'}), 400

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            query = """
            INSERT INTO device_logs (device_id, device_name, temperature, pressure, status, limit_switch_A, limit_switch_B, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            # Optional timestamp
            timestamp = data.get('timestamp')
            if not timestamp:
                from datetime import datetime, timedelta
                # Force IST by adding 5 hours 30 mins to UTC. This ensures it displays 
                # correctly even when running on Render's UTC-default servers.
                ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
                timestamp = ist_time.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute(query, (device_id, device_name, temp, pres, status_val, limitA, limitB, timestamp))
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
            if 'on_time' in result and result['on_time'] is not None:
                result['on_time'] = str(result['on_time'])
            if 'off_time' in result and result['off_time'] is not None:
                result['off_time'] = str(result['off_time'])
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
            if 'on_time' in r and r['on_time'] is not None:
                r['on_time'] = str(r['on_time'])
            if 'off_time' in r and r['off_time'] is not None:
                r['off_time'] = str(r['off_time'])
        return jsonify(results)
    return jsonify([]), 500

@app.route('/schedule', methods=['GET', 'POST'])
def schedule_data():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        if request.method == 'GET':
            cursor.execute("SELECT on_time, off_time FROM schedule_settings WHERE id = 1")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            if result:
                on_time_str = str(result['on_time']) if result['on_time'] is not None else '--:--:--'
                off_time_str = str(result['off_time']) if result['off_time'] is not None else '--:--:--'
                
                # Only keep HH:MM
                if on_time_str.count(':') == 2:
                    on_time_str = ":".join(on_time_str.split(':')[:2])
                if off_time_str.count(':') == 2:
                    off_time_str = ":".join(off_time_str.split(':')[:2])
                    
                # Format to HH:MM (adds leading 0 for single digit hour)
                if len(on_time_str) == 4: on_time_str = "0" + on_time_str
                if len(off_time_str) == 4: off_time_str = "0" + off_time_str

                return jsonify({'on_time': on_time_str, 'off_time': off_time_str})
            else:
                return jsonify({'on_time': '--:--', 'off_time': '--:--'})

        elif request.method == 'POST':
            data = request.json
            if not data or 'on_time' not in data or 'off_time' not in data:
                return jsonify({'status': 'error', 'message': 'Missing on_time or off_time fields'}), 400
            
            on_time = data['on_time'] + ':00' if len(data['on_time']) == 5 else data['on_time']
            off_time = data['off_time'] + ':00' if len(data['off_time']) == 5 else data['off_time']
            
            from datetime import datetime, timedelta
            ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
            timestamp = ist_time.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute(
                "UPDATE schedule_settings SET on_time = %s, off_time = %s WHERE id = 1",
                (on_time, off_time)
            )
            cursor.execute(
                "INSERT INTO schedule_history (on_time, off_time, timestamp) VALUES (%s, %s, %s)",
                (on_time, off_time, timestamp)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500

@app.route('/schedule-history', methods=['GET'])
def schedule_history_data():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM schedule_history ORDER BY id DESC LIMIT 50")
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        for r in results:
            if r.get('timestamp'):
                r['timestamp'] = r['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            if 'on_time' in r and r['on_time'] is not None:
                r['on_time'] = str(r['on_time'])
            if 'off_time' in r and r['off_time'] is not None:
                r['off_time'] = str(r['off_time'])
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
