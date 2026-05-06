CREATE DATABASE IF NOT EXISTS iot_monitoring;
USE iot_monitoring;

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
);

CREATE TABLE IF NOT EXISTS schedule_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    on_time VARCHAR(50),
    off_time VARCHAR(50),
    morning_time VARCHAR(50),
    evening_time VARCHAR(50),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insert default schedule if it doesn't exist
INSERT INTO schedule_history (on_time, off_time, morning_time, evening_time) 
SELECT '10', '10', '08:00', '18:00'
WHERE NOT EXISTS (SELECT 1 FROM schedule_history);
