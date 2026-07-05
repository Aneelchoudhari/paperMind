import { useState, useEffect } from 'react';
import { toast } from 'react-hot-toast';
import { api } from '../utils/api';

const TYPE_ICONS = { keyword: '📝', semantic: '🧠', hybrid: '⚡', qa: '💬' };

function HistoryItem({ item }) {
  const date = new Date(item.created_at).toLocaleString();
  return (
    <div className="result-item">
      <div className="result-meta" style={{ marginBottom: '0.5rem' }}>
        <span className="tag tag-cat">{TYPE_ICONS[item.query_type] || '🔍'} {item.query_type}</span>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{date}</span>
      </div>
      <div style={{ fontWeight: 500, fontSize: '0.95rem', marginBottom: item.answer_text ? '0.75rem' : 0 }}>
        {item.query_text}
      </div>
      {item.answer_text && (
        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', borderLeft: '2px solid var(--border-strong)', paddingLeft: '0.75rem', fontStyle: 'italic', lineHeight: 1.6 }}>
          {item.answer_text.length > 200 ? item.answer_text.slice(0, 200) + '…' : item.answer_text}
        </div>
      )}
    </div>
  );
}

export default function HistoryPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.history(50)
      .then(d => setItems(Array.isArray(d) ? d : []))
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1>History</h1>
        <p className="page-subtitle">Your recent searches and Q&A sessions</p>
      </div>

      {loading ? (
        <div className="empty-state"><span className="spinner" style={{ width: 36, height: 36 }} /></div>
      ) : items.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🕐</div>
          <div className="empty-title">No history yet</div>
          <p>Your searches and Q&A sessions will appear here</p>
        </div>
      ) : (
        <div className="scroll-list">
          {items.map(item => <HistoryItem key={item.id} item={item} />)}
        </div>
      )}
    </div>
  );
}
