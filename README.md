# Real-Time IoT Device Monitoring Web Application

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.12%2B-blue)
![Flask](https://img.shields.io/badge/Framework-Flask-orange)
![MySQL](https://img.shields.io/badge/Database-MySQL-4479A1)

## Overview
This project is a comprehensive Real-Time IoT Monitoring Application designed to listen for incoming telemetry data from varied devices, logging their performance metrics seamlessly into a backend and rendering an interactive visual dashboard for analytical review.

The backend leverages a **Flask REST API**, integrated with a lightweight and fast **MySQL** database for permanent storage. The frontend visualizes the system's heart rate in real-time utilizing **Chart.js**.

---

## 🏗️ Technology Stack

- **Frontend:** HTML5, CSS3, JavaScript (Vanilla ES6), Chart.js
- **Backend:** Python, Flask
- **Database:** Managed Cloud MySQL (e.g. Aiven, Railway, AWS RDS)
- **Deployment:** Render (via Gunicorn)

---

## 🚀 API & Integration

The backend provides several public REST endpoints for external IoT devices to offload their data stream securely.

- **Base URL:** `https://<your-render-project-url>.onrender.com`

### 1. Send Telemetry Data
- **Endpoint:** `POST /update`
- **Description:** Forwards incoming sensory data from your physical IoT device.
- **Headers:** `Content-Type: application/json`
- **Request Payload Example:**
```json
{
    "temperature": 28.5,
    "pressure": 101.3,
    "status": "ON",
    "limitA": true,
    "limitB": false
}
```
*Note: Include an optional `timestamp` key (Format: `YYYY-MM-DD HH:MM:SS`) or the database will automatically generate one for you.*

### 2. Fetch Latest Log
- **Endpoint:** `GET /latest`
- **Description:** Returns the single most recent log entry from the database.

### 3. Fetch Historical Data Logs
- **Endpoint:** `GET /history`
- **Description:** Returns an array containing the last 50 telemetry logs, optimized specifically for charting.

### 4. Health Check
- **Endpoint:** `GET /health`
- **Description:** Basic connectivity check and DB availability tracking.

---

## 🛠️ Setup Instructions (Local & Cloud)

### Prerequisites

- Python 3.12+
- A local MySQL server OR a Managed Cloud Provider (e.g., Railway MySQL)

### 1. Clone & Install
```bash
git clone https://github.com/your-username/iot-monitoring.git
cd iot-monitoring
pip install -r requirements.txt
```

### 2. Local Environment Configuration
Duplicate or create a `.env` file in the root directory. Configure your database access depending on your deployment model:

```ini
# .env
DB_HOST=your_cloud_mysql_host.example.com
DB_USER=your_username
DB_PASSWORD=your_secure_password
DB_NAME=your_db_name
DB_PORT=3306
```
*(If no `.env` is found, the system defaults dynamically to a standard local MySQL installation `root@localhost` with an empty password).*

### 3. Run the Server
The application manages its own data-modeling automatically on initialization. 

**Development (Local):**
```bash
python app.py
```

**Production (Render Configuration):**
Set the Start Command to:
```bash
gunicorn app:app
```

---


