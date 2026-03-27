import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useDropzone } from 'react-dropzone';

const API_URL = 'http://localhost:8000';

function TestPage() {
  const [files, setFiles] = useState([]);

  useEffect(() => {
    fetchFiles();
  }, []);

  const fetchFiles = async () => {
    try {
      const response = await axios.get(`${API_URL}/test/list`);
      setFiles(response.data.files || []);
    } catch (error) {
      console.error('Error:', error);
    }
  };

  const onDrop = async (acceptedFiles) => {
    const file = acceptedFiles[0];
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      await axios.post(`${API_URL}/upload/test`, formData);
      fetchFiles();
    } catch (error) {
      console.error('Error:', error);
    }
  };

  const { getRootProps, getInputProps } = useDropzone({ onDrop, maxFiles: 1 });

  return (
    <div>
      <h2>🔍 Проверка</h2>
      <div style={{ padding: '30px', border: '2px dashed #ccc', borderRadius: '8px', cursor: 'pointer', textAlign: 'center' }} {...getRootProps()}>
        <input {...getInputProps()} />
        <p>Перетащите файл для проверки</p>
      </div>
      
      <h3>Файлы ({files.length})</h3>
      {files.map((file, i) => (
        <div key={i}>📄 {file}</div>
      ))}
    </div>
  );
}

export default TestPage;