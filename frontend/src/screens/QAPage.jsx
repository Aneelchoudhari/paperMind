import { useState } from 'react';
import { toast } from 'react-hot-toast';
import { api } from '../utils/api';

function renderAnswerWithMarkers(text) {
  if (!text) return null;
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (m) return <sup key={i} className="citation-marker">{m[1]}</sup>;
    return <span key={i}>{part}</span>;
  });
}

function CitationCard({ citation }) {
  return (
    <div className="citation-item">
      <div className="citation-num">{citation.marker}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: '0.25rem' }}>
          {citation.paper_title || 'Unknown Paper'}
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {citation.page_number && <span className="tag tag-page">p.{citation.page_number}</span>}
          {citation.section_title && <span className="tag tag-section">{citation.section_title}</span>}
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '0.25rem' }}>
          {citation.chunk_id?.slice(0, 12)}…
        </div>
      </div>
    </div>
  );
}

const SAMPLE_QUESTIONS = [
  'How does self-attention reduce sequential computation?',
  'What is the main contribution of the LoRA paper?',
  'Explain the YOLO object detection approach',
  'What are the key findings about transformer scaling laws?',
];

export default function QAPage() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleAsk(q) {
    const queryText = q || question;
    if (!queryText.trim()) return;
    setLoading(true);
    setAnswer(null);
    try {
      const data = await api.qa({ question: queryText });
      setAnswer(data);
      if (!data.sufficient_evidence) {
        toast('No sufficient evidence found in your papers', { icon: '⚠️' });
      }
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Ask AI</h1>
        <p className="page-subtitle">Ask questions — get grounded answers with exact citations from your papers</p>
      </div>

      {/* Question input */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="form-group" style={{ marginBottom: '1rem' }}>
          <label className="label">Your Question</label>
          <textarea
            className="textarea"
            placeholder="e.g. How does self-attention reduce sequential computation?"
            value={question}
            onChange={e => setQuestion(e.target.value)}
            rows={3}
            onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) handleAsk(); }}
          />
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Ctrl+Enter to submit</div>
        </div>
        <button className="btn btn-primary" onClick={() => handleAsk()} disabled={loading || !question.trim()}>
          {loading ? <><span className="spinner" /> Thinking…</> : '💬 Ask PaperMind'}
        </button>
      </div>

      {/* Sample questions */}
      {!answer && !loading && (
        <div style={{ marginBottom: '2rem' }}>
          <div className="label" style={{ marginBottom: '0.75rem' }}>Try an example</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {SAMPLE_QUESTIONS.map((q, i) => (
              <button key={i} className="btn btn-secondary" style={{ fontSize: '0.8rem' }}
                onClick={() => { setQuestion(q); handleAsk(q); }}>
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
          <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>🤔</div>
          <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Searching and reasoning…</div>
          <p>Retrieving relevant passages, re-ranking, and generating a grounded answer</p>
          <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'center', gap: '0.5rem' }}>
            {['Retrieving…', 'Re-ranking…', 'Generating…'].map((s, i) => (
              <span key={i} className="tag tag-cat" style={{ animationDelay: `${i * 0.5}s` }}>{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Answer */}
      {answer && !loading && (
        <div>
          {/* Sufficiency indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
            <span className={`status-badge ${answer.sufficient_evidence ? 'status-ready' : 'status-failed'}`}>
              <span className="status-dot" />
              {answer.sufficient_evidence ? 'Evidence found' : 'Insufficient evidence'}
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {answer.citations?.length || 0} citation{answer.citations?.length !== 1 ? 's' : ''}
            </span>
          </div>

          {/* Answer text */}
          <div className="card" style={{ marginBottom: '1.5rem', background: 'linear-gradient(135deg, var(--bg-card), rgba(99,102,241,0.05))' }}>
            <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', alignItems: 'center' }}>
              <span style={{ fontSize: '1.25rem' }}>🧠</span>
              <h3>Answer</h3>
            </div>
            <div className="answer-text">
              {renderAnswerWithMarkers(answer.answer)}
            </div>
          </div>

          {/* Citations */}
          {answer.citations?.length > 0 && (
            <div className="card">
              <h3 style={{ marginBottom: '1rem' }}>📎 Sources</h3>
              <div className="citations-list">
                {answer.citations.map((c, i) => <CitationCard key={i} citation={c} />)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
