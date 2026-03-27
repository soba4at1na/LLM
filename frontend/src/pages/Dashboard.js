import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000';

function Dashboard() {
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 3000);
    return () => clearInterval(interval);
  }, []);

  const fetchMetrics = async () => {
    try {
      const response = await axios.get(`${API_URL}/metrics`);
      setMetrics(response.data);
    } catch (error) {
      console.error('Error:', error);
    }
  };

  return (
    <div>
      <h2>📊 Дашборд</h2>
      <div style={{ background: '#f0f0f0', padding: '15px', borderRadius: '8px' }}>
        {metrics ? (
          <div>
            <div>🖥️ CPU: {metrics.cpu_percent}%</div>
            <div>💾 RAM: {metrics.memory_used_gb}/{metrics.memory_total_gb} GB</div>
            {metrics.gpu_available && (
              <div>🎮 GPU: {metrics.gpu_utilization || 0}%</div>
            )}
          </div>
        ) : (
          <div>Загрузка...</div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;