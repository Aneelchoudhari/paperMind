import { useState } from 'react';
import { toast } from 'react-hot-toast';
import { api } from '../utils/api';

const MODES = ['hybrid', 'semantic', 'keyword'];

function ResultCard({ result, index }) {
  return (
    <div className="result-item" style={{ animationDelay: `${index * 50}ms` }}>
      <div className="result-meta">
        <span className="tag tag-paper">📄 {result.paper_title || 'Unknown Paper'}</span>
        {result.page_number && <span className="tag tag-page">p.{result.page_number}</span>}
        {result.section_title && <span className="tag tag-section">{result.section_title}</span>}
        <span className="tag tag-score">⚡ {(result.score * 100).toFixed(1)}%</span>
      </div>
      <p className="result-snippet">{result.text_snippet}</p>
    </div>
  );
}

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('hybrid');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await api.search({ query, mode, top_k: 10 });
      setResults(data);
      if (data.results.length === 0) toast('No results found for this query', { icon: '🔍' });
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Search Papers</h1>
        <p className="page-subtitle">Find relevant passages across all indexed papers</p>
      </div>

      {/* Search form */}
      <form onSubmit={handleSearch}>
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="search-bar" style={{ flexDirection: 'column', alignItems: 'stretch', gap: '1rem' }}>
            <div className="search-input-wrap">
              <span className="search-icon">🔍</span>
              <input
                className="search-input"
                placeholder="e.g. efficient attention mechanisms, LoRA fine-tuning…"
                value={query}
                onChange={e => setQuery(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
              <div className="mode-toggle">
                {MODES.map(m => (
                  <button key={m} type="button" className={`mode-btn${mode === m ? ' active' : ''}`} onClick={() => setMode(m)}>
                    {m === 'hybrid' ? '⚡ Hybrid' : m === 'semantic' ? '🧠 Semantic' : '📝 Keyword'}
                  </button>
                ))}
              </div>
              <button className="btn btn-primary" type="submit" disabled={loading || !query.trim()}>
                {loading ? <span className="spinner" /> : '🔍 Search'}
              </button>
            </div>
          </div>
        </div>
      </form>

      {/* Results */}
      {results && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3>{results.total_results} results</h3>
            <span className="tag tag-cat">{mode} mode</span>
          </div>
          {results.results.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">🔍</div>
              <div className="empty-title">No results found</div>
              <p>Try different keywords or switch search mode</p>
            </div>
          ) : (
            <div className="scroll-list">
              {results.results.map((r, i) => <ResultCard key={r.chunk_id} result={r} index={i} />)}
            </div>
          )}
        </div>
      )}

      {!results && !loading && (
        <div className="empty-state">
          <div className="empty-icon">💡</div>
          <div className="empty-title">Enter a query to search</div>
          <p><strong>Hybrid</strong> mode combines BM25 keyword matching with semantic vector similarity for best results</p>
        </div>
      )}
    </div>
  );
}
