CREATE DATABASE IF NOT EXISTS iot_monitoring;
USE iot_monitoring;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    phone VARCHAR(20) UNIQUE,
    password VARCHAR(255) NOT NULL
);

-- Note: Other tables (logs_table, schedule_table, schedule_history) 
-- will be initialized automatically by app.py's init_db() function.
