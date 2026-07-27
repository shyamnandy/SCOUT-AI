import { useState, useEffect } from 'react';
import { getNewsletters } from '../services/api';
import Icon from '../components/Icon';

export default function History() {
  const [newsletters, setNewsletters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedNl, setSelectedNl] = useState(null);

  useEffect(() => {
    getNewsletters({ limit: 50 })
      .then((res) => setNewsletters(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page" style={{ textAlign: 'center', paddingTop: 80 }}><p style={{ color: 'var(--text-muted)' }}>Loading newsletters...</p></div>;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <div className="page-eyebrow">Archive</div>
        <h1>Newsletter History</h1>
        <p>Browse your past curated newsletters</p>
      </div>

      {newsletters.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><Icon name="archive" size={22} /></div>
          <h3>No Newsletters Yet</h3>
          <p>Your newsletters will appear here once the AI starts delivering them</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: selectedNl ? '1fr 1fr' : '1fr', gap: 24 }}>
          <div className="newsletter-list">
            {newsletters.map((nl) => (
              <div
                key={nl.id}
                className={`glass-card newsletter-item ${selectedNl?.id === nl.id ? 'selected' : ''}`}
                onClick={() => setSelectedNl(nl)}
                style={selectedNl?.id === nl.id ? { borderColor: 'var(--accent)' } : {}}
              >
                <div className="newsletter-item-header">
                  <span className="newsletter-item-title">{nl.title}</span>
                  <span className="newsletter-item-date">
                    {new Date(nl.delivered_at).toLocaleDateString()} {new Date(nl.delivered_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                <div className="newsletter-item-meta">
                  <span><Icon name="grid" size={13} /> {nl.topic_name}</span>
                  <span><Icon name="mail" size={13} /> {nl.articles.length} articles</span>
                  <span className="chip" style={{ fontSize: 11 }}>{nl.delivery_status}</span>
                </div>
              </div>
            ))}
          </div>

          {selectedNl && (
            <div className="glass-card newsletter-preview">
              <h3 style={{ marginBottom: 16 }}>{selectedNl.title}</h3>
              <iframe
                srcDoc={selectedNl.html_content}
                title="Newsletter Preview"
                style={{ width: '100%', border: 'none', borderRadius: 'var(--radius-md)', minHeight: 500, background: '#0a0e1a' }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
