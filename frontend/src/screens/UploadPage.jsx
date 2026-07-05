import { useState, useCallback, useRef, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { toast } from 'react-hot-toast';
import { api } from '../utils/api';

const CATEGORIES = ['NLP', 'CV', 'RL', 'Multimodal', 'Theory', 'Systems', 'Other'];

function UploadItem({ item }) {
  const statusClass = `status-${item.status}`;
  return (
    <div className="result-item" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>{item.name}</div>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          {(item.size / 1024 / 1024).toFixed(2)} MB
          {item.category && ` · ${item.category}`}
        </div>
      </div>
      <span className={`status-badge ${statusClass}`}>
        <span className={`status-dot ${item.status === 'processing' ? 'pulse' : ''}`} />
        {item.status}
      </span>
      {item.paperId && (
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {item.paperId.slice(0, 8)}…
        </div>
      )}
    </div>
  );
}

export default function UploadPage() {
  const [uploads, setUploads] = useState([]);
  const [category, setCategory] = useState('');
  const [uploading, setUploading] = useState(false);
  const intervalsRef = useRef([]);

  // Clear all polling intervals when component unmounts
  useEffect(() => () => intervalsRef.current.forEach(clearInterval), []);

  const onDrop = useCallback(async (acceptedFiles) => {
    const pdfFiles = acceptedFiles.filter(f => f.type === 'application/pdf' || f.name.endsWith('.pdf'));
    if (pdfFiles.length === 0) { toast.error('Only PDF files are accepted'); return; }

    for (const file of pdfFiles) {
      const id = Math.random().toString(36).slice(2);
      const entry = { id, name: file.name, size: file.size, category, status: 'uploading', paperId: null };
      setUploads(u => [entry, ...u]);

      try {
        setUploading(true);
        const formData = new FormData();
        formData.append('file', file);
        if (category) formData.append('category', category);
        const res = await api.uploadPaper(formData);
        setUploads(u => u.map(x => x.id === id ? { ...x, status: 'processing', paperId: res.paper_id } : x));
        toast.success(`${file.name} uploaded — processing in background`);
        // Poll status
        pollStatus(id, res.paper_id);
      } catch (err) {
        toast.error(err.message);
        setUploads(u => u.map(x => x.id === id ? { ...x, status: 'failed' } : x));
      } finally {
        setUploading(false);
      }
    }
  }, [category]);

  async function pollStatus(localId, paperId) {
    const interval = setInterval(async () => {
      try {
        const st = await api.getPaperStatus(paperId);
        setUploads(u => u.map(x => x.id === localId ? { ...x, status: st.status } : x));
        if (st.status === 'ready') {
          toast.success('Paper ready! You can now search and ask questions about it.');
          clearInterval(interval);
        } else if (st.status === 'failed') {
          toast.error(`Processing failed: ${st.error_message || 'Unknown error'}`);
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
      }
    }, 3000);
    intervalsRef.current.push(interval);
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: true,
  });

  return (
    <div>
      <div className="page-header">
        <h1>Upload Papers</h1>
        <p className="page-subtitle">Drag & drop PDF research papers to index them for search and QA</p>
      </div>

      {/* Category selector */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="form-group">
          <label className="label">Category (optional)</label>
          <select className="select" value={category} onChange={e => setCategory(e.target.value)} style={{ maxWidth: 280 }}>
            <option value="">— Select category —</option>
            {CATEGORIES.map(c => <option key={c}>{c}</option>)}
          </select>
        </div>
      </div>

      {/* Drop zone */}
      <div {...getRootProps()} className={`dropzone${isDragActive ? ' drag-active' : ''}`}>
        <input {...getInputProps()} />
        <div className="dropzone-icon">📄</div>
        <div className="dropzone-title">
          {isDragActive ? 'Drop PDFs here…' : 'Drag & drop PDF files here'}
        </div>
        <div className="dropzone-sub">or click to browse · Max 50MB per file</div>
      </div>

      {/* Upload queue */}
      {uploads.length > 0 && (
        <div style={{ marginTop: '2rem' }}>
          <h3 style={{ marginBottom: '1rem' }}>Upload Queue ({uploads.length})</h3>
          <div className="scroll-list">
            {uploads.map(item => <UploadItem key={item.id} item={item} />)}
          </div>
        </div>
      )}
    </div>
  );
}
