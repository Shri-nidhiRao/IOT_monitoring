let chart;
let maxPoints = 20;

function initCharts() {
const ctx = document.getElementById('chartCanvas').getContext('2d');
// Fixed chart ID mismatch - no pressureChart needed
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Temperature (°C)',
                data: [],
                borderColor: '#00ff88',
                backgroundColor: 'rgba(0,255,136,0.1)',
                tension: 0.4,
                fill: true,
                yAxisID: 'y'
            }, {
                label: 'Pressure (kPa)',
                data: [],
                borderColor: '#ffaa00',
                backgroundColor: 'rgba(255,170,0,0.1)',
                tension: 0.4,
                fill: true,
                yAxisID: 'y1'
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
                    position: 'left',
                    beginAtZero: true,
                    title: { display: true, text: 'Temperature (°C)', color: '#00ff88' },
                    grid: { color: 'rgba(0,255,136,0.1)' },
                    ticks: { color: '#aaa' }
                },
                y1: {
                    position: 'right',
                    beginAtZero: true,
                    title: { display: true, text: 'Pressure (kPa)', color: '#ffaa00' },
                    grid: { drawOnChartArea: false },
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
            document.getElementById('status').textContent = data.status;
            document.getElementById('last-updated').textContent = new Date(data.timestamp).toLocaleString();
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

        }
    } catch (e) {
        console.error('Latest update error:', e);
    }
}

async function updateHistory() {
    try {
        const response = await fetch('/history');
        if (!response.ok) return;
        const history = await response.json();
        const labels = history.map(h => new Date(h.timestamp).toLocaleTimeString()).slice(0, maxPoints);
        const temps = history.map(h => h.temperature).slice(0, maxPoints);
        const pressures = history.map(h => h.pressure).slice(0, maxPoints);

        chart.data.labels = labels;
        chart.data.datasets[0].data = temps;
        chart.data.datasets[1].data = pressures;
        chart.update('active');
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
                <td>${row.temperature.toFixed(1)}</td>
                <td>${row.pressure.toFixed(1)}</td>
                <td>${row.status}</td>
                <td>${row.limit_switch_A ? 'ON' : 'OFF'}</td>
                <td>${row.limit_switch_B ? 'ON' : 'OFF'}</td>
                <td>${new Date(row.timestamp).toLocaleString()}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error('Logs update error:', e);
    }
}

document.querySelectorAll('.sidebar a').forEach(link => {
    link.addEventListener('click', async (e) => {
        e.preventDefault();
        const isDashboard = link.getAttribute('href') === '#dashboard';
        document.getElementById('dashboard').style.display = isDashboard ? 'block' : 'none';
        document.getElementById('logs').style.display = isDashboard ? 'none' : 'block';
        document.querySelector('.sidebar .active').classList.remove('active');
        link.parentElement.classList.add('active');
        if (!isDashboard) updateLogs();
    });
});

initCharts();
setInterval(updateLatest, 1000);
setInterval(updateHistory, 5000);
setInterval(updateLogs, 10000);
updateLatest();

