import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useDropzone } from 'react-dropzone';

const API_URL = 'http://localhost:8000';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [metrics, setMetrics] = useState(null);
  const [gpuStatus, setGpuStatus] = useState(null);
  const [trainFiles, setTrainFiles] = useState([]);
  const [testFiles, setTestFiles] = useState([]);
  const [uploadingTrain, setUploadingTrain] = useState(false);
  const [uploadingTest, setUploadingTest] = useState(false);
  const [analysisResults, setAnalysisResults] = useState(null);
  const [text, setText] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [datasetStats, setDatasetStats] = useState({ total: 0, correct: 0, incorrect: 0 });

  useEffect(() => {
    fetchMetrics();
    fetchGpuStatus();
    fetchFiles();
    fetchDatasetStats();
    const interval = setInterval(() => {
      fetchMetrics();
      fetchGpuStatus();
      fetchFiles();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchMetrics = async () => {
    try {
      const response = await axios.get(`${API_URL}/metrics`);
      setMetrics(response.data);
    } catch (error) {
      console.error('Error fetching metrics:', error);
    }
  };

  const fetchGpuStatus = async () => {
    try {
      const response = await axios.get(`${API_URL}/gpu-status`);
      setGpuStatus(response.data);
    } catch (error) {
      console.error('Error fetching GPU status:', error);
    }
  };

  const fetchFiles = async () => {
    try {
      const [trainRes, testRes] = await Promise.all([
        axios.get(`${API_URL}/train/list`),
        axios.get(`${API_URL}/test/list`)
      ]);
      setTrainFiles(trainRes.data.files || []);
      setTestFiles(testRes.data.files || []);
    } catch (error) {
      console.error('Error fetching files:', error);
    }
  };

  const fetchDatasetStats = async () => {
    try {
      const response = await axios.get(`${API_URL}/dataset/stats`);
      setDatasetStats(response.data);
    } catch (error) {
      console.error('Error fetching dataset stats:', error);
    }
  };

  const analyzeText = async () => {
    if (!text.trim()) return;
    setLoading(true);
    try {
      const response = await axios.post(`${API_URL}/analyze`, { text });
      setResult(response.data);
    } catch (error) {
      console.error('Error analyzing text:', error);
      alert('Ошибка анализа');
    }
    setLoading(false);
  };

  const onDropTrain = async (acceptedFiles) => {
    const file = acceptedFiles[0];
    const formData = new FormData();
    formData.append('file', file);
    setUploadingTrain(true);
    
    try {
      await axios.post(`${API_URL}/upload/train`, formData);
      alert(`✅ ${file.name} загружен для обучения`);
      fetchFiles();
      fetchDatasetStats();
    } catch (error) {
      console.error('Error:', error);
      alert(`❌ Ошибка загрузки ${file.name}`);
    }
    setUploadingTrain(false);
  };

  const onDropTest = async (acceptedFiles) => {
    const file = acceptedFiles[0];
    const formData = new FormData();
    formData.append('file', file);
    setUploadingTest(true);
    
    try {
      const response = await axios.post(`${API_URL}/upload/test`, formData);
      alert(`✅ ${file.name} загружен для проверки`);
      setAnalysisResults(response.data);
      fetchFiles();
    } catch (error) {
      console.error('Error:', error);
      alert(`❌ Ошибка загрузки ${file.name}`);
    }
    setUploadingTest(false);
  };

  const deleteTrainFile = async (filename) => {
    try {
      await axios.delete(`${API_URL}/train/delete/${filename}`);
      alert(`✅ ${filename} удалён`);
      fetchFiles();
      fetchDatasetStats();
    } catch (error) {
      console.error('Error:', error);
      alert(`❌ Ошибка удаления ${filename}`);
    }
  };

  const deleteTestFile = async (filename) => {
    try {
      await axios.delete(`${API_URL}/test/delete/${filename}`);
      alert(`✅ ${filename} удалён`);
      fetchFiles();
    } catch (error) {
      console.error('Error:', error);
      alert(`❌ Ошибка удаления ${filename}`);
    }
  };

  const viewResults = async (filename) => {
    try {
      const response = await axios.get(`${API_URL}/results/test/${filename}`);
      setAnalysisResults(response.data);
    } catch (error) {
      console.error('Error:', error);
      alert(`❌ Не удалось загрузить результаты для ${filename}`);
    }
  };

  const { getRootProps: getTrainRootProps, getInputProps: getTrainInputProps } = useDropzone({ onDrop: onDropTrain, maxFiles: 1 });
  const { getRootProps: getTestRootProps, getInputProps: getTestInputProps } = useDropzone({ onDrop: onDropTest, maxFiles: 1 });

  const tabStyle = (tab) => ({
    padding: '10px 20px',
    cursor: 'pointer',
    backgroundColor: activeTab === tab ? '#4CAF50' : '#f0f0f0',
    color: activeTab === tab ? 'white' : '#333',
    border: 'none',
    borderRadius: '8px',
    fontSize: '16px',
    transition: 'all 0.3s'
  });

  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif', maxWidth: '1400px', margin: '0 auto' }}>
      <h1 style={{ textAlign: 'center', marginBottom: '20px' }}>📝 Технический анализатор текстов</h1>
      
      <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', marginBottom: '20px', flexWrap: 'wrap' }}>
        <button onClick={() => setActiveTab('dashboard')} style={tabStyle('dashboard')}>📊 Дашборд</button>
        <button onClick={() => setActiveTab('train')} style={tabStyle('train')}>📚 Обучение</button>
        <button onClick={() => setActiveTab('test')} style={tabStyle('test')}>🔍 Проверка</button>
        <button onClick={() => setActiveTab('analyze')} style={tabStyle('analyze')}>✍️ Анализ текста</button>
      </div>

      {/* Дашборд */}
      {activeTab === 'dashboard' && (
        <div>
          <div style={{ background: '#f0f0f0', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
            <h3>📊 Системный мониторинг</h3>
            {metrics ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
                <div>🖥️ CPU: {metrics.cpu_percent}%</div>
                <div>💾 RAM: {metrics.memory_used_gb}/{metrics.memory_total_gb} GB</div>
                <div>💽 Disk: {metrics.disk_used_gb}/{metrics.disk_total_gb} GB</div>
              </div>
            ) : (
              <div>Загрузка...</div>
            )}
          </div>

          <div style={{ background: '#2d2d2d', color: '#fff', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
            <h3>🎮 GPU Статус</h3>
            {gpuStatus && gpuStatus.available ? (
              <div>
                <div>✅ {gpuStatus.message}</div>
                {gpuStatus.models && (
                  <div>📦 Загруженные модели: {gpuStatus.models.join(', ')}</div>
                )}
                <div style={{ fontSize: '12px', marginTop: '8px', color: '#aaa' }}>
                  Для детальной загрузки GPU используйте: docker exec ollama nvidia-smi
                </div>
              </div>
            ) : (
              <div>⚠️ {gpuStatus?.message || 'GPU не обнаружен'}</div>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            <div style={{ background: '#e8f5e9', padding: '15px', borderRadius: '8px', textAlign: 'center' }}>
              <h3>📚 Датасет</h3>
              <div style={{ fontSize: '32px', fontWeight: 'bold' }}>{datasetStats.total}</div>
              <div>всего примеров</div>
              <div>✅ {datasetStats.correct} | ⚠️ {datasetStats.incorrect}</div>
            </div>
            <div style={{ background: '#fff3e0', padding: '15px', borderRadius: '8px', textAlign: 'center' }}>
              <h3>📈 Статус</h3>
              <div>📄 Обучающих файлов: {trainFiles.length}</div>
              <div>🔍 Для проверки: {testFiles.length}</div>
            </div>
          </div>
        </div>
      )}

      {/* Обучение */}
      {activeTab === 'train' && (
        <div>
          <h3>📚 Загрузка файлов для обучения</h3>
          <div style={{ padding: '30px', border: '2px dashed #ccc', borderRadius: '8px', cursor: 'pointer', textAlign: 'center', marginBottom: '20px', background: '#fafafa' }} {...getTrainRootProps()}>
            <input {...getTrainInputProps()} />
            <p>📚 Перетащите файл сюда или нажмите для выбора</p>
            <small>Поддерживаются: .txt, .docx, .pdf, .json</small>
          </div>

          {uploadingTrain && <div style={{ background: '#e3f2fd', padding: '10px', borderRadius: '8px', marginBottom: '10px' }}>⏳ Обработка файла...</div>}

          <h4>📁 Обучающие файлы ({trainFiles.length})</h4>
          <div style={{ maxHeight: '400px', overflow: 'auto' }}>
            {trainFiles.map((file, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px', borderBottom: '1px solid #eee' }}>
                <span>📄 {file}</span>
                <button onClick={() => deleteTrainFile(file)} style={{ padding: '4px 12px', backgroundColor: '#f44336', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                  Удалить
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Проверка */}
      {activeTab === 'test' && (
        <div>
          <h3>🔍 Загрузка файлов для проверки</h3>
          <div style={{ padding: '30px', border: '2px dashed #ccc', borderRadius: '8px', cursor: 'pointer', textAlign: 'center', marginBottom: '20px', background: '#fafafa' }} {...getTestRootProps()}>
            <input {...getTestInputProps()} />
            <p>🔍 Перетащите файл сюда или нажмите для выбора</p>
            <small>Поддерживаются: .txt, .docx, .pdf, .json</small>
          </div>

          {uploadingTest && <div style={{ background: '#e3f2fd', padding: '10px', borderRadius: '8px', marginBottom: '10px' }}>⏳ Обработка файла...</div>}

          {analysisResults && analysisResults.results && (
            <div style={{ background: '#e8f4f8', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
              <h4>📋 Результаты анализа</h4>
              <div>Всего абзацев: {analysisResults.total_paragraphs}</div>
              <div>Проанализировано: {analysisResults.analyzed}</div>
              <details>
                <summary style={{ cursor: 'pointer' }}>Показать детали</summary>
                {analysisResults.results && analysisResults.results.slice(0, 5).map((res, i) => (
                  <div key={i} style={{ padding: '8px', borderBottom: '1px solid #ccc' }}>
                    <div><strong>Абзац {res.paragraph}:</strong> {res.text?.substring(0, 100)}...</div>
                    <div>Статус: {res.result?.is_correct ? '✅ Корректен' : '⚠️ Есть проблемы'}</div>
                  </div>
                ))}
              </details>
            </div>
          )}

          <h4>📁 Файлы для проверки ({testFiles.length})</h4>
          <div style={{ maxHeight: '400px', overflow: 'auto' }}>
            {testFiles.map((file, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px', borderBottom: '1px solid #eee' }}>
                <span>📄 {file}</span>
                <div>
                  <button onClick={() => viewResults(file)} style={{ padding: '4px 12px', marginRight: '8px', backgroundColor: '#2196f3', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                    Показать
                  </button>
                  <button onClick={() => deleteTestFile(file)} style={{ padding: '4px 12px', backgroundColor: '#f44336', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                    Удалить
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Анализ текста */}
      {activeTab === 'analyze' && (
        <div>
          <h3>✍️ Анализ текста</h3>
          <textarea
            rows="6"
            style={{ width: '100%', padding: '10px', fontSize: '14px', borderRadius: '4px', border: '1px solid #ccc' }}
            placeholder="Введите текст для анализа..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <button
            onClick={analyzeText}
            disabled={loading || !text.trim()}
            style={{ marginTop: '10px', padding: '10px 20px', backgroundColor: '#4CAF50', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', width: '100%' }}
          >
            {loading ? 'Анализирую...' : '🔬 Анализировать'}
          </button>

          {result && (
            <div style={{ marginTop: '20px', padding: '15px', background: '#e8f4f8', borderRadius: '8px' }}>
              <h4>📋 Результат анализа</h4>
              <p><strong>Статус:</strong> {result.is_correct ? '✅ Корректен' : '⚠️ Есть проблемы'}</p>
              <p><strong>Уверенность:</strong> {(result.confidence * 100).toFixed(0)}%</p>
              {result.analysis && <p><strong>Анализ:</strong> {result.analysis}</p>}
            </div>
          )}
        </div>
      )}

      <div style={{ marginTop: '20px', textAlign: 'center', fontSize: '12px', color: '#666' }}>
        ⚡ GPU: {gpuStatus?.available ? 'Активен' : 'Не обнаружен'} | Модель: qwen2.5:7b
      </div>
    </div>
  );
}

export default App;