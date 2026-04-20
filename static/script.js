let temperatureChart;
let pressureChart;
let maxPoints = 20;

function initCharts() {
    const tempCtx = document.getElementById('temperatureChart').getContext('2d');
    temperatureChart = new Chart(tempCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Temperature (°C)',
                data: [],
                borderColor: '#00ff88',
                backgroundColor: 'rgba(0,255,136,0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 1000,
                easing: 'easeOutQuart'
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    ticks: { color: '#aaa' }
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Temperature (°C)', color: '#00ff88' },
                    grid: { color: 'rgba(0,255,136,0.1)' },
                    ticks: { color: '#aaa' }
                }
            },
            plugins: {
                legend: {
                    labels: { color: '#e0e0e0', font: { family: 'Poppins' } }
                }
            }
        }
    });

    const presCtx = document.getElementById('pressureChart').getContext('2d');
    pressureChart = new Chart(presCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Pressure (kPa)',
                data: [],
                borderColor: '#ffaa00',
                backgroundColor: 'rgba(255,170,0,0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 1000,
                easing: 'easeOutQuart'
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    ticks: { color: '#aaa' }
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Pressure (kPa)', color: '#ffaa00' },
                    grid: { color: 'rgba(255,170,0,0.1)' },
                    ticks: { color: '#aaa' }
                }
            },
            plugins: {
                legend: {
                    labels: { color: '#e0e0e0', font: { family: 'Poppins' } }
                }
            }
        }
    });
}

async function updateLatest() {
    try {
        const response = await fetch('/latest');
        if (!response.ok) return;
        const data = await response.json();
        if (data.id) {
            document.getElementById('temp').textContent = data.temperature.toFixed(1) + ' °C';
            document.getElementById('pressure').textContent = data.pressure.toFixed(1) + ' kPa';
            document.getElementById('last-updated').textContent = new Date(data.timestamp).toLocaleString();
            
            document.getElementById('disp-on-time').textContent = data.on_time || '--';
            document.getElementById('disp-off-time').textContent = data.off_time || '--';
            document.getElementById('disp-morning-time').textContent = data.morning_time || '--:--';
            document.getElementById('disp-evening-time').textContent = data.evening_time || '--:--';
            document.getElementById('disp-motor-status').textContent = data.motor_status || 'Unknown';
            
            const limitAEl = document.getElementById('limitA');
            const limitBEl = document.getElementById('limitB');
            limitAEl.textContent = data.limit_switch_A ? 'ON' : 'OFF';
            limitBEl.textContent = data.limit_switch_B ? 'ON' : 'OFF';
            limitAEl.className = data.limit_switch_A ? 'metric-value on' : 'metric-value off';
            limitBEl.className = data.limit_switch_B ? 'metric-value on' : 'metric-value off';

            const tempStatus = document.getElementById('temp-status');
            const pressureStatus = document.getElementById('pressure-status');
            tempStatus.className = data.temperature > 30 ? 'metric-status danger' : 'metric-status normal';
            pressureStatus.className = data.pressure > 100 ? 'metric-status danger' : 'metric-status normal';

            const statusDot = document.querySelector('.status-dot');
            if (statusDot) statusDot.className = 'status-dot online';
        }
    } catch (e) {
        console.error('Latest update error:', e);
        const statusDot = document.querySelector('.status-dot');
        if (statusDot) statusDot.className = 'status-dot offline';
    }
}

async function updateHistory() {
    try {
        const response = await fetch('/history');
        if (!response.ok) return;
        const history = await response.json();
        const labels = history.map(h => new Date(h.timestamp).toLocaleTimeString()).slice(0, maxPoints).reverse();
        const temps = history.map(h => h.temperature).slice(0, maxPoints).reverse();
        const pressures = history.map(h => h.pressure).slice(0, maxPoints).reverse();

        temperatureChart.data.labels = labels;
        temperatureChart.data.datasets[0].data = temps;
        temperatureChart.update('active');

        pressureChart.data.labels = labels;
        pressureChart.data.datasets[0].data = pressures;
        pressureChart.update('active');
    } catch (e) {
        console.error('History update error:', e);
    }
}

async function updateLogs() {
    try {
        const response = await fetch('/history');
        if (!response.ok) return;
        const history = await response.json();
        const tbody = document.querySelector('#logsTable tbody');
        tbody.innerHTML = '';
        history.slice(0, 50).forEach(row => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${row.id}</td>
                <td>${row.device_id || 'Unknown'}</td>
                <td>${row.device_name || 'Unknown'}</td>
                <td>${row.temperature.toFixed(1)}</td>
                <td>${row.pressure.toFixed(1)}</td>
                <td>${row.limit_switch_A ? 'ON' : 'OFF'}</td>
                <td>${row.limit_switch_B ? 'ON' : 'OFF'}</td>
                <td>${row.on_time || '--'}</td>
                <td>${row.off_time || '--'}</td>
                <td>${row.morning_time || '--:--'}</td>
                <td>${row.evening_time || '--:--'}</td>
                <td>${row.motor_status || 'Unknown'}</td>
                <td>${new Date(row.timestamp).toLocaleString()}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error('Logs update error:', e);
    }
}

async function fetchSchedule() {
    try {
        const response = await fetch('/schedule');
        if (!response.ok) return;
        const data = await response.json();
        if (data.on_time && data.on_time !== '--') {
            document.getElementById('on_time').value = data.on_time;
        }
        if (data.off_time && data.off_time !== '--') {
            document.getElementById('off_time').value = data.off_time;
        }
    } catch (e) {
        console.error('Failed to fetch schedule:', e);
    }
}

document.getElementById('save-schedule')?.addEventListener('click', async () => {
    const onTime = document.getElementById('on_time').value;
    const offTime = document.getElementById('off_time').value;
    const btn = document.getElementById('save-schedule');
    const originalText = btn.textContent;
    btn.textContent = 'Saving...';
    btn.disabled = true;

    try {
        const response = await fetch('/schedule', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                on_time: onTime, 
                off_time: offTime
            })
        });
        
        if (response.ok) {
            btn.textContent = 'Saved!';
            setTimeout(() => { btn.textContent = originalText; btn.disabled = false; }, 2000);
        } else {
            console.error('Failed to save schedule');
            btn.textContent = 'Error';
            setTimeout(() => { btn.textContent = originalText; btn.disabled = false; }, 2000);
        }
    } catch (e) {
        console.error('Schedule save error:', e);
        btn.textContent = 'Error';
        setTimeout(() => { btn.textContent = originalText; btn.disabled = false; }, 2000);
    }
});

async function updateScheduleHistory() {
    try {
        const response = await fetch('/schedule-history');
        if (!response.ok) return;
        const history = await response.json();
        const tbody = document.querySelector('#scheduleHistoryTable tbody');
        tbody.innerHTML = '';
        history.slice(0, 50).forEach(row => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${row.id}</td>
                <td>${row.on_time || '--'}</td>
                <td>${row.off_time || '--'}</td>
                <td>${row.morning_time ? row.morning_time.split(':').slice(0,2).join(':') : '--:--'}</td>
                <td>${row.evening_time ? row.evening_time.split(':').slice(0,2).join(':') : '--:--'}</td>
                <td>${new Date(row.timestamp).toLocaleString()}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error('Schedule history update error:', e);
    }
}

document.querySelectorAll('.sidebar a').forEach(link => {
    link.addEventListener('click', async (e) => {
        e.preventDefault();
        const href = link.getAttribute('href');
        document.getElementById('dashboard').style.display = href === '#dashboard' ? 'block' : 'none';
        document.getElementById('logs').style.display = href === '#logs' ? 'block' : 'none';
        document.getElementById('schedule-history').style.display = href === '#schedule-history' ? 'block' : 'none';
        
        document.querySelector('.sidebar .active').classList.remove('active');
        link.parentElement.classList.add('active');
        
        if (href === '#logs') updateLogs();
        if (href === '#schedule-history') updateScheduleHistory();
    });
});

initCharts();
fetchSchedule();
setInterval(updateLatest, 1000);
setInterval(updateHistory, 5000);
setInterval(updateLogs, 10000);
updateLatest();

