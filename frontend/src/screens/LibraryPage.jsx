import { useState, useEffect } from 'react';
import { toast } from 'react-hot-toast';
import { api } from '../utils/api';

function StatusBadge({ status }) {
  return (
    <span className={`status-badge status-${status}`}>
      <span className={`status-dot ${status === 'processing' ? 'pulse' : ''}`} />
      {status}
    </span>
  );
}

export default function LibraryPage() {
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [deleting, setDeleting] = useState(null);

  async function load() {
    try {
      const data = await api.listPapers({ limit: 50 });
      setPapers(Array.isArray(data) ? data : []);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleDelete(id) {
    if (!confirm('Delete this paper and all its chunks?')) return;
    setDeleting(id);
    try {
      await api.deletePaper(id);
      setPapers(p => p.filter(x => x.id !== id));
      toast.success('Paper deleted');
    } catch (err) {
      toast.error(err.message);
    } finally {
      setDeleting(null);
    }
  }

  const filtered = papers.filter(p =>
    !search || (p.title || '').toLowerCase().includes(search.toLowerCase()) ||
    (p.authors || []).some(a => a.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h1>Library</h1>
          <p className="page-subtitle">{papers.length} papers indexed</p>
        </div>
        <button className="btn btn-secondary" onClick={load}>↻ Refresh</button>
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <input
          className="search-input"
          placeholder="🔍  Filter by title or author…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ borderRadius: 'var(--radius-sm)' }}
        />
      </div>

      {loading ? (
        <div className="empty-state"><span className="spinner" style={{ width: 32, height: 32 }} /></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📚</div>
          <div className="empty-title">No papers yet</div>
          <p>Upload some PDFs to get started</p>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Authors</th>
                <th>Year</th>
                <th>Category</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(p => (
                <tr key={p.id}>
                  <td>
                    <div style={{ fontWeight: 600, fontSize: '0.875rem', maxWidth: 320 }}>
                      {p.title || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Processing…</span>}
                    </div>
                    {p.doi && <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{p.doi}</div>}
                  </td>
                  <td style={{ maxWidth: 200 }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {(p.authors || []).slice(0, 3).join(', ')}{p.authors?.length > 3 && ' +more'}
                    </div>
                  </td>
                  <td>{p.publication_year || '—'}</td>
                  <td>{p.category ? <span className="tag tag-cat">{p.category}</span> : '—'}</td>
                  <td><StatusBadge status={p.status} /></td>
                  <td>
                    <button
                      className="btn btn-danger"
                      style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem' }}
                      onClick={() => handleDelete(p.id)}
                      disabled={deleting === p.id}
                    >
                      {deleting === p.id ? <span className="spinner" /> : '🗑'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
