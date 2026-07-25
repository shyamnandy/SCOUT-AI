import { useState } from 'react';
import Icon from './Icon';

export default function TopicForm({ topic, onSubmit, onClose }) {
  const [name, setName] = useState(topic?.name || '');
  const [keywordInput, setKeywordInput] = useState('');
  const [keywords, setKeywords] = useState(topic?.keywords || []);
  const [category, setCategory] = useState(topic?.category || 'technology');
  const [deliveryTimes, setDeliveryTimes] = useState(topic?.delivery_times || ['08:00']);
  const [lifecycle, setLifecycle] = useState(topic?.lifecycle || 'perpetual');
  const [expirationDate, setExpirationDate] = useState(topic?.expiration_date ? topic.expiration_date.split('T')[0] : '');
  const [loading, setLoading] = useState(false);

  const addKeyword = () => {
    if (keywordInput.trim() && !keywords.includes(keywordInput.trim())) {
      setKeywords([...keywords, keywordInput.trim()]);
      setKeywordInput('');
    }
  };

  const removeKeyword = (kw) => setKeywords(keywords.filter((k) => k !== kw));

  const addDeliveryTime = () => setDeliveryTimes([...deliveryTimes, '12:00']);
  const updateTime = (i, val) => { const t = [...deliveryTimes]; t[i] = val; setDeliveryTimes(t); };
  const removeTime = (i) => setDeliveryTimes(deliveryTimes.filter((_, idx) => idx !== i));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || keywords.length === 0) return;
    setLoading(true);
    await onSubmit({
      name, keywords, category, delivery_times: deliveryTimes, lifecycle,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      expiration_date: lifecycle === 'ephemeral' && expirationDate ? new Date(expirationDate).toISOString() : null,
    });
    setLoading(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="glass-card modal animate-fade" onClick={(e) => e.stopPropagation()}>
        <h2>{topic ? 'Edit Topic' : 'New Topic'}</h2>
        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <label>Topic Name</label>
            <input className="input-field" placeholder="e.g. AI Research Updates" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>

          <div className="input-group">
            <label>Keywords</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input className="input-field" placeholder="Type & press Enter" value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addKeyword(); } }} />
              <button type="button" className="btn btn-secondary btn-sm" onClick={addKeyword}>Add</button>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
              {keywords.map((kw) => (
                <span key={kw} className="chip">{kw} <span className="chip-remove" onClick={() => removeKeyword(kw)}>×</span></span>
              ))}
            </div>
          </div>

          <div className="input-group">
            <label>Category</label>
            <select className="input-field" value={category} onChange={(e) => setCategory(e.target.value)}>
              {['technology','world_news','finance','sports','entertainment','science'].map(c => (
                <option key={c} value={c}>{c.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</option>
              ))}
            </select>
          </div>

          <div className="input-group">
            <label>Delivery Times</label>
            {deliveryTimes.map((t, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
                <input type="time" className="input-field" value={t} onChange={(e) => updateTime(i, e.target.value)} />
                {deliveryTimes.length > 1 && <button type="button" className="btn btn-danger btn-sm" onClick={() => removeTime(i)}>×</button>}
              </div>
            ))}
            <button type="button" className="btn btn-secondary btn-sm" onClick={addDeliveryTime}>+ Add Time</button>
          </div>

          <div className="input-group">
            <label>Lifecycle</label>
            <div style={{ display: 'flex', gap: 16 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 14 }}>
                <input type="radio" name="lifecycle" value="perpetual" checked={lifecycle === 'perpetual'} onChange={() => setLifecycle('perpetual')} /> <Icon name="infinity" size={14} /> Perpetual
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 14 }}>
                <input type="radio" name="lifecycle" value="ephemeral" checked={lifecycle === 'ephemeral'} onChange={() => setLifecycle('ephemeral')} /> <Icon name="calendar" size={14} /> Finite
              </label>
            </div>
          </div>

          {lifecycle === 'ephemeral' && (
            <div className="input-group">
              <label>Expiration Date</label>
              <input type="date" className="input-field" value={expirationDate} onChange={(e) => setExpirationDate(e.target.value)} required />
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading || !name.trim() || keywords.length === 0}>
              {loading ? 'Saving...' : 'Save Topic'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
