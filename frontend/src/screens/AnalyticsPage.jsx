import { useState, useEffect } from 'react';
import { toast } from 'react-hot-toast';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { api } from '../utils/api';

const COLORS = ['#6366f1', '#a855f7', '#06b6d4', '#10b981', '#f59e0b', '#f43f5e', '#3b82f6', '#ec4899'];

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload?.length) {
    return (
      <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, padding: '0.75rem 1rem', fontSize: '0.85rem' }}>
        <div style={{ color: 'var(--text-muted)', marginBottom: 2 }}>{label}</div>
        <div style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{payload[0].value} papers</div>
      </div>
    );
  }
  return null;
};

export default function AnalyticsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.analytics()
      .then(d => setData(d))
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div>
      <div className="page-header"><h1>Analytics</h1></div>
      <div className="empty-state"><span className="spinner" style={{ width: 40, height: 40 }} /></div>
    </div>
  );

  if (!data) return null;

  return (
    <div>
      <div className="page-header">
        <h1>Analytics</h1>
        <p className="page-subtitle">Overview of your paper library · Cached for 5 minutes</p>
      </div>

      {/* Stat cards */}
      <div className="card-grid" style={{ marginBottom: '2rem' }}>
        <div className="stat-card">
          <div className="stat-icon">📚</div>
          <div className="stat-value">{data.total_papers}</div>
          <div className="stat-label">Total Papers</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">🧩</div>
          <div className="stat-value">{(data.total_chunks || 0).toLocaleString()}</div>
          <div className="stat-label">Text Chunks</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">🏷️</div>
          <div className="stat-value">{data.by_category?.length || 0}</div>
          <div className="stat-label">Categories</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">👤</div>
          <div className="stat-value">{data.top_authors?.length || 0}</div>
          <div className="stat-label">Unique Authors</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
        {/* By year */}
        {data.by_year?.length > 0 && (
          <div className="card">
            <h3 style={{ marginBottom: '1.25rem' }}>📅 Papers by Year</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={data.by_year.map(d => ({ name: d.year || 'N/A', count: d.count }))} barCategoryGap="30%">
                <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="count" fill="var(--accent)" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* By category */}
        {data.by_category?.length > 0 && (
          <div className="card">
            <h3 style={{ marginBottom: '1.25rem' }}>🏷️ By Category</h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={data.by_category.map(d => ({ name: d.category || 'Uncategorized', value: d.count }))}
                  cx="50%" cy="50%" outerRadius={70} innerRadius={35}
                  dataKey="value" nameKey="name" paddingAngle={3}>
                  {data.by_category.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Legend iconType="circle" iconSize={8} formatter={(v) => <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>{v}</span>} />
                <Tooltip contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        {/* Top authors */}
        {data.top_authors?.length > 0 && (
          <div className="card">
            <h3 style={{ marginBottom: '1rem' }}>👤 Top Authors</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {data.top_authors.map((a, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginRight: '0.5rem' }}>#{i+1}</span>
                    {a.author}
                  </div>
                  <span className="tag tag-paper">{a.count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Top queries */}
        {data.top_queries?.length > 0 && (
          <div className="card">
            <h3 style={{ marginBottom: '1rem' }}>🔍 Top Queries</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {data.top_queries.map((q, i) => (
                <div key={i} style={{ padding: '0.5rem 0.75rem', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginRight: '0.5rem' }}>#{i+1}</span>
                  {q.length > 60 ? q.slice(0, 60) + '…' : q}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {data.total_papers === 0 && (
        <div className="empty-state" style={{ marginTop: '2rem' }}>
          <div className="empty-icon">📊</div>
          <div className="empty-title">No data yet</div>
          <p>Upload and process some papers to see analytics</p>
        </div>
      )}
    </div>
  );
}
