import app
conn = app.get_db_connection()
if conn:
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE device_logs")
    conn.commit()
    cursor.close()
    conn.close()
    print("Database cleared successfully!")
else:
    print("Failed to connect to database.")
