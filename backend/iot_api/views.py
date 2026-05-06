import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

import mysql.connector
from mysql.connector import Error

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
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
    conn = get_db_connection(include_db=True)
    db_name = DB_CONFIG.get('database', 'iot_monitoring')
    
    if not conn:
        conn = get_db_connection(include_db=False)
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name};")
            except Error as e:
                print(f"Skipping DB creation: {e}")
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
                    on_time VARCHAR(50),
                    off_time VARCHAR(50),
                    morning_time VARCHAR(50),
                    evening_time VARCHAR(50),
                    motor_status VARCHAR(50),
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            try:
                cursor.execute("ALTER TABLE logs_table DROP COLUMN limit_switch_A;")
            except Error:
                pass
            try:
                cursor.execute("ALTER TABLE logs_table DROP COLUMN limit_switch_B;")
            except Error:
                pass
            
            try:
                cursor.execute("ALTER TABLE logs_table DROP COLUMN status;")
            except Error:
                pass
            
            try:
                cursor.execute("DROP TABLE IF EXISTS schedule_table;")
            except Error:
                pass
            
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
            
            for tbl in ['schedule_history']:
                try:
                    cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN morning_time VARCHAR(50);")
                except Error: pass
                try:
                    cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN evening_time VARCHAR(50);")
                except Error: pass
                try:
                    cursor.execute(f"ALTER TABLE {tbl} MODIFY COLUMN on_time VARCHAR(50);")
                except Error: pass
                try:
                    cursor.execute(f"ALTER TABLE {tbl} MODIFY COLUMN off_time VARCHAR(50);")
                except Error: pass
            
            cursor.execute("SELECT COUNT(*) FROM schedule_history")
            (count,) = cursor.fetchone()
            if count == 0:
                cursor.execute("INSERT INTO schedule_history (on_time, off_time, morning_time, evening_time) VALUES ('10', '10', '08:00', '18:00')")

            conn.commit()
            print("Database and tables initialized.")
        except Error as e:
            print(f"Table creation error: {e}")
            
        cursor.close()
        conn.close()
    else:
        print("Failed to connect to DB for initialization.")

# Auto-initialize DB on module load
try:
    init_db()
except Exception as e:
    print(f"Startup DB init failed: {e}")

# Helpers
def format_seconds_ms(val_str):
    if not val_str or val_str == '--': return '--'
    try:
        f = float(val_str)
        return f"{int(f):02d}:{int(round((f % 1) * 100)):02d}"
    except ValueError:
        pass
    val_str = str(val_str).strip()
    parts = val_str.split(':')
    if len(parts) == 3:
        try:
            return f"{int(parts[2]):02d}:00"
        except: pass
    if len(parts) == 2:
        try:
            sec = int(parts[0])
            ms_str = parts[1]
            if len(ms_str) >= 3:
                ms = int(ms_str[:2])
            else:
                ms = int(ms_str)
            return f"{sec:02d}:{ms:02d}"
        except: pass
    return val_str

def format_min_sec(val_str):
    if not val_str or val_str in ('--', '--:--'): return '--:--'
    try:
        f = float(val_str)
        return f"{int(f):02d}:{int(round((f % 1) * 100)):02d}"
    except ValueError:
        pass
    parts = str(val_str).split(':')
    if len(parts) >= 2:
        try:
            return f"{int(parts[0]):02d}:{int(parts[1][:2]):02d}"
        except: pass
    return str(val_str)

def format_history_results(results):
    for r in results:
        if r.get('timestamp'):
            r['timestamp'] = r['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        if 'on_time' in r and r['on_time'] is not None:
            r['on_time'] = format_seconds_ms(r['on_time'])
        if 'off_time' in r and r['off_time'] is not None:
            r['off_time'] = format_seconds_ms(r['off_time'])
        if 'morning_time' in r and r['morning_time'] is not None:
            r['morning_time'] = format_min_sec(r['morning_time'])
        if 'evening_time' in r and r['evening_time'] is not None:
            r['evening_time'] = format_min_sec(r['evening_time'])
    return results

def format_latest_result(result):
    if result:
        if result.get('timestamp'):
            result['timestamp'] = result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        if 'on_time' in result and result['on_time'] is not None:
            result['on_time'] = format_seconds_ms(result['on_time'])
        if 'off_time' in result and result['off_time'] is not None:
            result['off_time'] = format_seconds_ms(result['off_time'])
        if 'morning_time' in result and result['morning_time'] is not None:
            result['morning_time'] = format_min_sec(result['morning_time'])
        if 'evening_time' in result and result['evening_time'] is not None:
            result['evening_time'] = format_min_sec(result['evening_time'])
    return result

# VIEWS

def test_http(request):
    return JsonResponse({
        'status': 'success',
        'message': 'HTTP connection working!',
        'protocol': request.scheme,
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'esp32_ready': True
    }, status=200)

@csrf_exempt
def update_data_http(request):
    try:
        if request.method == 'GET':
            device_id = str(request.GET.get('api_key', 'ESP32_001'))
            device_name = str(request.GET.get('device_name', 'SolarTracker_GSM'))
            temp = float(request.GET.get('field1', 0.0))
            pres = float(request.GET.get('field2', 0.0))
            on_time = str(request.GET.get('field3', '05:00'))
            off_time = str(request.GET.get('field4', '10:00'))
            morning_time = str(request.GET.get('field5', '08:00'))
            evening_time = str(request.GET.get('field6', '18:00'))
            motor_status = str(request.GET.get('field7', 'WAIT'))
        else:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'status': 'error', 'message': 'No JSON payload'}, status=400)
            
            if not data:
                return JsonResponse({'status': 'error', 'message': 'No JSON payload'}, status=400)
            
            device_id = str(data.get('mainid', 'ESP32_001'))
            device_name = str(data.get('Device_name', 'SolarTracker_GSM'))
            temp = float(data.get('temperature', 0.0))
            pres = float(data.get('pressure', 0.0))
            on_time = str(data.get('on_time', '05:00'))
            off_time = str(data.get('off_time', '10:00'))
            morning_time = str(data.get('morning_time', '08:00'))
            evening_time = str(data.get('evening_time', '18:00'))
            motor_status = str(data.get('motor_status', 'WAIT'))
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
            timestamp = ist_time.strftime('%Y-%m-%d %H:%M:%S')
            
            query = """
            INSERT INTO logs_table (device_id, device_name, temperature, pressure, 
            on_time, off_time, morning_time, evening_time, motor_status, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(query, (device_id, device_name, temp, pres, 
                                  on_time, off_time, morning_time, evening_time, motor_status, timestamp))
            
            cursor.execute("SELECT on_time, off_time, morning_time, evening_time FROM schedule_history ORDER BY id DESC LIMIT 1")
            schedule_row = cursor.fetchone()
            
            conn.commit()
            cursor.close()
            conn.close()
            
            if schedule_row:
                return JsonResponse({
                    'status': 'success',
                    'on_time': str(schedule_row[0]) if schedule_row[0] else '10',
                    'off_time': str(schedule_row[1]) if schedule_row[1] else '10',
                    'morning_time': str(schedule_row[2]) if schedule_row[2] else '08:00',
                    'evening_time': str(schedule_row[3]) if schedule_row[3] else '18:00'
                })
            
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Database connection failed'}, status=500)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def schedule_data_http(request):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT on_time, off_time, morning_time, evening_time FROM schedule_history ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return JsonResponse({
                'on_time': str(result['on_time']) if result['on_time'] else '10',
                'off_time': str(result['off_time']) if result['off_time'] else '10',
                'morning_time': str(result['morning_time']) if result['morning_time'] else '08:00',
                'evening_time': str(result['evening_time']) if result['evening_time'] else '18:00'
            })
    return JsonResponse({'on_time': '10', 'off_time': '10', 'morning_time': '08:00', 'evening_time': '18:00'})

@csrf_exempt
def update_data(request):
    try:
        if request.method == 'GET':
            def safe_float(val, default=0.0):
                try:
                    return float(val) if (val and str(val).strip() != "") else default
                except ValueError:
                    return default

            device_id = str(request.GET.get('api_key', 'Unknown_Auth'))
            device_name = str(request.GET.get('device_name', 'ThingSpeak_Node'))
            pres = safe_float(request.GET.get('field1', 0.0))
            temp = safe_float(request.GET.get('field2', 0.0))
            
            m_float = safe_float(request.GET.get('field3', 0.0))
            e_float = safe_float(request.GET.get('field4', 0.0))
            morning_time = f"{int(m_float):02d}:{round((m_float % 1) * 100):02d}"
            evening_time = f"{int(e_float):02d}:{round((e_float % 1) * 100):02d}"
            
            on_f = safe_float(request.GET.get('field5', 0.0))
            off_f = safe_float(request.GET.get('field6', 0.0))
            on_time = f"{int(on_f):02d}:{int(round((on_f % 1) * 100)):02d}"
            off_time = f"{int(off_f):02d}:{int(round((off_f % 1) * 100)):02d}"
            
            motor_status = 'Unknown'
            timestamp = None
        else:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'status': 'error', 'message': 'No JSON payload provided'}, status=400)
                
            if not data:
                return JsonResponse({'status': 'error', 'message': 'No JSON payload provided'}, status=400)
            try:
                device_id = str(data.get('mainid', 'Unknown'))
                device_name = str(data.get('Device_name', data.get('device_name', 'Unknown')))
                temp = float(data.get('temperature', 0.0))
                pres = float(data.get('pressure', 0.0))
                
                on_time = str(data.get('on_time', data.get('on time', '0')))
                off_time = str(data.get('off_time', data.get('off time', '0')))
                morning_time = str(data.get('morning_time', data.get('morning time', '--:--')))
                evening_time = str(data.get('evening_time', data.get('evening time', '--:--')))
                motor_status = str(data.get('motor_status', data.get('motor status', 'Unknown')))
                timestamp = data.get('timestamp')
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'Invalid data types provided'}, status=400)

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            query = """
            INSERT INTO logs_table (device_id, device_name, temperature, pressure, on_time, off_time, morning_time, evening_time, motor_status, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            if not timestamp:
                ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
                timestamp = ist_time.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute(query, (device_id, device_name, temp, pres, on_time, off_time, morning_time, evening_time, motor_status, timestamp))
            
            cursor.execute("SELECT on_time, off_time, morning_time, evening_time FROM schedule_history ORDER BY id DESC LIMIT 1")
            schedule_row = cursor.fetchone()

            conn.commit()
            cursor.close()
            conn.close()

            if schedule_row:
                return JsonResponse({
                    'status': 'success',
                    'on_time': str(schedule_row[0]) if schedule_row[0] is not None else '--',
                    'off_time': str(schedule_row[1]) if schedule_row[1] is not None else '--',
                    'morning_time': str(schedule_row[2]) if schedule_row[2] is not None else '--:--',
                    'evening_time': str(schedule_row[3]) if schedule_row[3] is not None else '--:--'
                })

            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Database connection failed'}, status=500)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def latest_data(request):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM logs_table ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return JsonResponse(format_latest_result(result))
    return JsonResponse({}, status=404)

def latest_by_id(request, device_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM logs_table WHERE device_id = %s ORDER BY id DESC LIMIT 1", (device_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return JsonResponse(format_latest_result(result))
    return JsonResponse({}, status=404)

def latest_by_name(request, device_name):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM logs_table WHERE device_name = %s ORDER BY id DESC LIMIT 1", (device_name,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return JsonResponse(format_latest_result(result))
    return JsonResponse({}, status=404)

def history_data(request):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM logs_table ORDER BY id DESC LIMIT 50")
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return JsonResponse(format_history_results(results), safe=False)
    return JsonResponse([], safe=False, status=500)

def history_by_id(request, device_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM logs_table WHERE device_id = %s ORDER BY id DESC LIMIT 50", (device_id,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return JsonResponse(format_history_results(results), safe=False)
    return JsonResponse([], safe=False, status=500)

def history_by_name(request, device_name):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM logs_table WHERE device_name = %s ORDER BY id DESC LIMIT 50", (device_name,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return JsonResponse(format_history_results(results), safe=False)
    return JsonResponse([], safe=False, status=500)

@csrf_exempt
def schedule_data(request):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        if request.method == 'GET':
            cursor.execute("SELECT on_time, off_time, morning_time, evening_time FROM schedule_history ORDER BY id DESC LIMIT 1")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            if result:
                on_time_str = str(result['on_time']) if result['on_time'] is not None else '--'
                off_time_str = str(result['off_time']) if result['off_time'] is not None else '--'
                morning_time_str = str(result['morning_time']) if result['morning_time'] is not None else '--:--'
                evening_time_str = str(result['evening_time']) if result['evening_time'] is not None else '--:--'
                return JsonResponse({
                    'on_time': on_time_str, 
                    'off_time': off_time_str, 
                    'morning_time': morning_time_str, 
                    'evening_time': evening_time_str
                })
            else:
                return JsonResponse({
                    'on_time': '--', 'off_time': '--', 'morning_time': '--:--', 'evening_time': '--:--'
                })

        elif request.method == 'POST':
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'status': 'error', 'message': 'Missing JSON body'}, status=400)
                
            if not data or 'on_time' not in data or 'off_time' not in data:
                return JsonResponse({'status': 'error', 'message': 'Missing on_time or off_time fields'}, status=400)
            
            on_time = str(data['on_time'])
            off_time = str(data['off_time'])
            morning_time = str(data.get('morning_time', '--:--'))
            evening_time = str(data.get('evening_time', '--:--'))
            
            ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
            timestamp = ist_time.strftime('%Y-%m-%d %H:%M:%S')

            try:
                cursor.execute(
                    "INSERT INTO schedule_history (on_time, off_time, morning_time, evening_time, timestamp) VALUES (%s, %s, %s, %s, %s)",
                    (on_time, off_time, morning_time, evening_time, timestamp)
                )
                conn.commit()
                cursor.close()
                conn.close()
                return JsonResponse({'status': 'success'})
            except Exception as e:
                print(f"Schedule API Crash: {e}")
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Database connection failed'}, status=500)

def schedule_history_data(request):
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
        return JsonResponse(results, safe=False)
    return JsonResponse([], safe=False, status=500)

def health(request):
    return JsonResponse({'status': 'healthy', 'db': 'available' if get_db_connection() else 'error'})
