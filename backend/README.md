# Real-Time IoT Device Monitoring Application

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.12%2B-blue)
![Django](https://img.shields.io/badge/Framework-Django-092E20)
![MySQL](https://img.shields.io/badge/Database-MySQL-4479A1)

## Overview
This project is a comprehensive Real-Time IoT Monitoring Application designed to listen for incoming telemetry data from varied devices, logging their performance metrics seamlessly into a backend and rendering an interactive visual dashboard for analytical review.

The system is decoupled into two independent parts:
1. **Frontend:** Pure HTML/JS dashboard visualizing system telemetry in real-time utilizing **Chart.js**.
2. **Backend:** A robust **Django REST API** integrated with a lightweight and fast **MySQL** database for permanent storage.

---

## 🏗️ Technology Stack

- **Frontend:** HTML5, CSS3, JavaScript (Vanilla ES6), Chart.js
- **Backend:** Python, Django, Django CORS Headers
- **Database:** MySQL
- **Deployment:** Standard WSGI (e.g. Gunicorn)

---

## 🚀 API & Integration

The backend provides several public REST endpoints for external IoT devices to offload their data stream securely.

- **Base URL:** `https://<your-backend-api-url.com>`

### 1. Send Telemetry Data
- **Endpoint:** `POST /update`
- **Description:** Forwards incoming sensory data from your physical IoT device.
- **Headers:** `Content-Type: application/json`
- **Request Payload Example:**
```json
{
    "mainid": "NODE_ALPHA_01",
    "Device_name": "SolarTracker_1",
    "temperature": 28.5,
    "pressure": 101.3,
    "on_time": "05:00",
    "off_time": "10:00",
    "morning_time": "08:00",
    "evening_time": "18:00",
    "motor_status": "WAIT"
}
```

### 2. Fetch Active Schedule Matrix
- **Endpoint:** `GET /schedule`
- **Description:** Allows your external device to query precisely when the physical hardware triggers should toggle.

### 3. Fetch Latest Log
- **Endpoint:** `GET /latest`
- **Description:** Returns the single most recent hardware data entry matrix.

### 4. Fetch Historical Data Logs
- **Endpoint:** `GET /history`
- **Description:** Returns an array containing the last 50 telemetry logs, optimized specifically for charting.

### 5. Fetch Schedule History
- **Endpoint:** `GET /schedule-history`
- **Description:** Retrieves the chronological logging of when the dashboard configurations were manually altered or reset.

---

## 🛠️ Setup & Hosting Instructions

### 1. Backend (Django API)
The backend is designed to be hosted on any standard Python provider (Render, AWS, Heroku, etc.).

1. Navigate to the `backend/` directory.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your production environment variables (usually in your host's dashboard):
   - `DB_HOST`
   - `DB_USER`
   - `DB_PASSWORD`
   - `DB_NAME`
   - `DB_PORT`
4. Start the production server using WSGI:
   ```bash
   gunicorn config.wsgi:application
   ```

### 2. Frontend (Dashboard)
The frontend is completely decoupled and static.
1. Navigate to `frontend/script.js` and update `const API_BASE = "https://your-backend-api-url.com";` to point to your deployed Django backend.
2. Host the `frontend/` folder on any static site hosting service (Vercel, Netlify, GitHub Pages, etc.). No build step is required!
