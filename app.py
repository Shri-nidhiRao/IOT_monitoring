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
                CREATE TABLE IF NOT EXISTS logs_table (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    device_id VARCHAR(50),
                    device_name VARCHAR(100),
                    temperature FLOAT NOT NULL,
                    pressure FLOAT NOT NULL,
                    limit_switch_A BOOLEAN NOT NULL,
                    limit_switch_B BOOLEAN NOT NULL,
                    on_time VARCHAR(50),
                    off_time VARCHAR(50),
                    morning_time VARCHAR(50),
                    evening_time VARCHAR(50),
                    motor_status VARCHAR(50),
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Safely drop status from previously built tables
            try:
                cursor.execute("ALTER TABLE logs_table DROP COLUMN status;")
            except Error:
                pass
            
            # Create scheduling tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedule_table (
                    id INT PRIMARY KEY,
                    on_time VARCHAR(50),
                    off_time VARCHAR(50),
                    morning_time VARCHAR(50),
                    evening_time VARCHAR(50)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedule_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    on_time VARCHAR(50),
                    off_time VARCHAR(50),
                    morning_time VARCHAR(50),
                    evening_time VARCHAR(50),
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Seed default schedule if empty
            cursor.execute("SELECT COUNT(*) FROM schedule_table WHERE id = 1")
            (count,) = cursor.fetchone()
            if count == 0:
                cursor.execute("INSERT INTO schedule_table (id, on_time, off_time, morning_time, evening_time) VALUES (1, '10', '10', '08:00', '18:00')")

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

@app.route('/update', methods=['GET', 'POST'])
def update_data():
    try:
        if request.method == 'GET':
            def safe_float(val, default=0.0):
                try:
                    return float(val) if (val and str(val).strip() != "") else default
                except ValueError:
                    return default

            # Handle ThingSpeak Style GET Request from the hardware
            device_id = str(request.args.get('api_key', 'Unknown_Auth'))
            device_name = str(request.args.get('device_name', 'ThingSpeak_Node'))
            pres = safe_float(request.args.get('field1', 0.0))
            temp = safe_float(request.args.get('field2', 0.0))
            
            # Math conversion: field3 sending 11.30 -> "11:30"
            m_float = safe_float(request.args.get('field3', 0.0))
            e_float = safe_float(request.args.get('field4', 0.0))
            morning_time = f"{int(m_float):02d}:{round((m_float % 1) * 100):02d}"
            evening_time = f"{int(e_float):02d}:{round((e_float % 1) * 100):02d}"
            
            # Build SS:MS formatting for on/off durations
            on_f = safe_float(request.args.get('field5', 0.0))
            off_f = safe_float(request.args.get('field6', 0.0))
            on_time = f"{int(on_f):02d}:{int(round((on_f % 1) * 1000)):03d}"
            off_time = f"{int(off_f):02d}:{int(round((off_f % 1) * 1000)):03d}"
            
            limitA = False
            limitB = False
            motor_status = 'Unknown'
            timestamp = None
        else:
            data = request.json
            if not data:
                return jsonify({'status': 'error', 'message': 'No JSON payload provided'}), 400
            # Validate data types
            try:
                device_id = str(data.get('mainid', 'Unknown'))
                device_name = str(data.get('Device_name', data.get('device_name', 'Unknown')))
                temp = float(data.get('temperature', 0.0))
                pres = float(data.get('pressure', 0.0))
                limitA = bool(data.get('limitA', False))
                limitB = bool(data.get('limitB', False))
                
                # Added new payload variable extractors with robust defaults
                on_time = str(data.get('on_time', data.get('on time', '0')))
                off_time = str(data.get('off_time', data.get('off time', '0')))
                morning_time = str(data.get('morning_time', data.get('morning time', '--:--')))
                evening_time = str(data.get('evening_time', data.get('evening time', '--:--')))
                motor_status = str(data.get('motor_status', data.get('motor status', 'Unknown')))
                timestamp = data.get('timestamp')
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Invalid data types provided'}), 400

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            query = """
            INSERT INTO logs_table (device_id, device_name, temperature, pressure, limit_switch_A, limit_switch_B, on_time, off_time, morning_time, evening_time, motor_status, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            # Optional timestamp
            if not timestamp:
                from datetime import datetime, timedelta
                # Force IST by adding 5 hours 30 mins to UTC. This ensures it displays 
                # correctly even when running on Render's UTC-default servers.
                ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
                timestamp = ist_time.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute(query, (device_id, device_name, temp, pres, limitA, limitB, on_time, off_time, morning_time, evening_time, motor_status, timestamp))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def format_history_results(results):
    for r in results:
        if r.get('timestamp'):
            r['timestamp'] = r['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        if 'on_time' in r and r['on_time'] is not None:
            r['on_time'] = str(r['on_time'])
        if 'off_time' in r and r['off_time'] is not None:
            r['off_time'] = str(r['off_time'])
    return results

def format_latest_result(result):
    if result:
        if result.get('timestamp'):
            result['timestamp'] = result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        if 'on_time' in result and result['on_time'] is not None:
            result['on_time'] = str(result['on_time'])
        if 'off_time' in result and result['off_time'] is not None:
            result['off_time'] = str(result['off_time'])
    return result

@app.route('/latest', methods=['GET'])
def latest_data():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM logs_table ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return jsonify(format_latest_result(result))
    return jsonify({}), 404

@app.route('/latest/id/<string:device_id>', methods=['GET'])
def latest_by_id(device_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM logs_table WHERE device_id = %s ORDER BY id DESC LIMIT 1", (device_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return jsonify(format_latest_result(result))
    return jsonify({}), 404

@app.route('/latest/name/<string:device_name>', methods=['GET'])
def latest_by_name(device_name):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM logs_table WHERE device_name = %s ORDER BY id DESC LIMIT 1", (device_name,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return jsonify(format_latest_result(result))
    return jsonify({}), 404

@app.route('/history', methods=['GET'])
def history_data():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM logs_table ORDER BY id DESC LIMIT 50")
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(format_history_results(results))
    return jsonify([]), 500

@app.route('/history/id/<string:device_id>', methods=['GET'])
def history_by_id(device_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM logs_table WHERE device_id = %s ORDER BY id DESC LIMIT 50", (device_id,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(format_history_results(results))
    return jsonify([]), 500

@app.route('/history/name/<string:device_name>', methods=['GET'])
def history_by_name(device_name):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM logs_table WHERE device_name = %s ORDER BY id DESC LIMIT 50", (device_name,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(format_history_results(results))
    return jsonify([]), 500

@app.route('/schedule', methods=['GET', 'POST'])
def schedule_data():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        if request.method == 'GET':
            cursor.execute("SELECT on_time, off_time, morning_time, evening_time FROM schedule_table WHERE id = 1")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            if result:
                on_time_str = str(result['on_time']) if result['on_time'] is not None else '--'
                off_time_str = str(result['off_time']) if result['off_time'] is not None else '--'
                morning_time_str = str(result['morning_time']) if result['morning_time'] is not None else '--:--'
                evening_time_str = str(result['evening_time']) if result['evening_time'] is not None else '--:--'
                return jsonify({'on_time': on_time_str, 'off_time': off_time_str, 'morning_time': morning_time_str, 'evening_time': evening_time_str})
            else:
                return jsonify({'on_time': '--', 'off_time': '--', 'morning_time': '--:--', 'evening_time': '--:--'})

        elif request.method == 'POST':
            data = request.json
            if not data or 'on_time' not in data or 'off_time' not in data:
                return jsonify({'status': 'error', 'message': 'Missing on_time or off_time fields'}), 400
            
            on_time = str(data['on_time'])
            off_time = str(data['off_time'])
            morning_time = str(data.get('morning_time', '--:--'))
            evening_time = str(data.get('evening_time', '--:--'))
            
            from datetime import datetime, timedelta
            ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
            timestamp = ist_time.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute(
                "UPDATE schedule_table SET on_time = %s, off_time = %s, morning_time = %s, evening_time = %s WHERE id = 1",
                (on_time, off_time, morning_time, evening_time)
            )
            cursor.execute(
                "INSERT INTO schedule_history (on_time, off_time, morning_time, evening_time, timestamp) VALUES (%s, %s, %s, %s, %s)",
                (on_time, off_time, morning_time, evening_time, timestamp)
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
