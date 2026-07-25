import { useState, useEffect } from 'react';
import Icon from './Icon';

const CATEGORIES = ['technology', 'world_news', 'finance', 'sports', 'entertainment', 'science'];

export default function TopicConfirmCard({ topic, onAdd, onDiscard, saving }) {
  const [name, setName] = useState('');
  const [keywordInput, setKeywordInput] = useState('');
  const [keywords, setKeywords] = useState([]);
  const [category, setCategory] = useState('technology');
  const [lifecycle, setLifecycle] = useState('perpetual');
  const [expirationDate, setExpirationDate] = useState('');

  useEffect(() => {
    if (!topic) return;
    setName(topic.name || '');
    setKeywords(topic.keywords || []);
    setCategory(topic.category || 'technology');
    setLifecycle(topic.suggested_lifecycle || 'perpetual');
    setExpirationDate('');
  }, [topic]);

  if (!topic) {
    return (
      <div className="glass-card confirm-card-placeholder">
        <Icon name="check" size={22} style={{ marginBottom: 10, opacity: 0.4 }} />
        <p>Confirm a topic in the chat and it'll show up here to review before you save it.</p>
      </div>
    );
  }

  const addKeyword = () => {
    if (keywordInput.trim() && !keywords.includes(keywordInput.trim())) {
      setKeywords([...keywords, keywordInput.trim()]);
      setKeywordInput('');
    }
  };
  const removeKeyword = (kw) => setKeywords(keywords.filter((k) => k !== kw));

  const handleAdd = () => {
    if (!name.trim() || keywords.length === 0) return;
    onAdd({
      name,
      keywords,
      category,
      lifecycle,
      // Unscheduled — the user drags it into a time slot on the dashboard.
      delivery_times: [],
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      expiration_date: lifecycle === 'ephemeral' && expirationDate ? new Date(expirationDate).toISOString() : null,
    });
  };

  return (
    <div className="glass-card confirm-card animate-fade">
      <h3>Review Topic</h3>

      <div className="input-group" style={{ marginBottom: 16 }}>
        <label>Name</label>
        <input className="input-field" value={name} onChange={(e) => setName(e.target.value)} />
      </div>

      <div className="input-group" style={{ marginBottom: 16 }}>
        <label>Keywords</label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            className="input-field"
            placeholder="Type & press Enter"
            value={keywordInput}
            onChange={(e) => setKeywordInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addKeyword(); } }}
          />
          <button type="button" className="btn btn-secondary btn-sm" onClick={addKeyword}>Add</button>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
          {keywords.map((kw) => (
            <span key={kw} className="chip">{kw} <span className="chip-remove" onClick={() => removeKeyword(kw)}>×</span></span>
          ))}
        </div>
      </div>

      <div className="input-group" style={{ marginBottom: 16 }}>
        <label>Category</label>
        <select className="input-field" value={category} onChange={(e) => setCategory(e.target.value)}>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}</option>
          ))}
        </select>
      </div>

      <div className="input-group" style={{ marginBottom: 16 }}>
        <label>Lifecycle</label>
        <div style={{ display: 'flex', gap: 16 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 14 }}>
            <input type="radio" name="cc-lifecycle" checked={lifecycle === 'perpetual'} onChange={() => setLifecycle('perpetual')} /> <Icon name="infinity" size={14} /> Perpetual
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 14 }}>
            <input type="radio" name="cc-lifecycle" checked={lifecycle === 'ephemeral'} onChange={() => setLifecycle('ephemeral')} /> <Icon name="calendar" size={14} /> Event-based
          </label>
        </div>
      </div>

      {lifecycle === 'ephemeral' && (
        <div className="input-group" style={{ marginBottom: 16 }}>
          <label>End Date</label>
          <input type="date" className="input-field" value={expirationDate} onChange={(e) => setExpirationDate(e.target.value)} />
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Leave blank to set it later — the topic will be created paused until you do.
          </span>
        </div>
      )}

      <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
        <button className="btn btn-secondary" onClick={onDiscard} disabled={saving}>Discard</button>
        <button
          className="btn btn-primary"
          style={{ flex: 1 }}
          onClick={handleAdd}
          disabled={saving || !name.trim() || keywords.length === 0}
        >
          {saving ? 'Adding...' : 'Add to My Topics'}
        </button>
      </div>

      <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-muted)', textAlign: 'center' }}>
        You'll pick delivery times by dragging it into a slot on the dashboard.
      </div>
    </div>
  );
}
