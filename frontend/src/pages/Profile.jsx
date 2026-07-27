import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { updatePreferences, updateApiKeys, deleteAccount, getErrorMessage } from '../services/api';
import Icon from '../components/Icon';

const PROVIDERS = [
  {
    field: 'resend_api_key',
    hasField: 'has_resend_key',
    name: 'Resend',
    icon: 'mail',
    required: true,
    placeholder: 're_...',
    getUrl: 'https://resend.com/api-keys',
    getLabel: 'resend.com/api-keys',
    blurb: 'Powers newsletter delivery. Required before you can start a chat — the shared key can only email its own account owner.',
  },
  {
    field: 'groq_api_key',
    hasField: 'has_groq_key',
    name: 'Groq',
    icon: 'chat',
    required: true,
    placeholder: 'gsk_...',
    getUrl: 'https://console.groq.com/keys',
    getLabel: 'console.groq.com/keys',
    blurb: 'Powers the onboarding chat and AI curation. Required before you can start a chat.',
  },
  {
    field: 'tavily_api_key',
    hasField: 'has_tavily_key',
    name: 'Tavily',
    icon: 'search',
    required: true,
    placeholder: 'tvly-...',
    getUrl: 'https://app.tavily.com/home',
    getLabel: 'app.tavily.com',
    blurb: 'Powers news search for curation. Required before you can start a chat — the shared key has a monthly usage cap shared by every user.',
  },
];

export default function Profile() {
  const { user, setUser, logout } = useAuth();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [keyInputs, setKeyInputs] = useState({ resend_api_key: '', groq_api_key: '', tavily_api_key: '' });
  const [keysSaving, setKeysSaving] = useState(false);
  const [keysMsg, setKeysMsg] = useState('');
  const [toast, setToast] = useState(null);
  const [highlightKeys, setHighlightKeys] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  const navigate = useNavigate();
  const location = useLocation();
  const keysCardRef = useRef(null);

  // Arriving here with a redirect toast (e.g. from the locked chat input) —
  // surface it, scroll the keys card into view, and clear the nav state so
  // a refresh/back-nav doesn't replay it.
  useEffect(() => {
    if (location.state?.toast) {
      setToast(location.state.toast);
      setHighlightKeys(true);
      keysCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      navigate(location.pathname, { replace: true, state: {} });
      const t1 = setTimeout(() => setToast(null), 6000);
      const t2 = setTimeout(() => setHighlightKeys(false), 2200);
      return () => { clearTimeout(t1); clearTimeout(t2); };
    }
  }, [location.state]);

  if (!user) return null;

  const saveKeys = async () => {
    setKeysSaving(true);
    setKeysMsg('');
    setError('');
    const payload = {};
    if (keyInputs.resend_api_key) payload.resend_api_key = keyInputs.resend_api_key;
    if (keyInputs.groq_api_key) payload.groq_api_key = keyInputs.groq_api_key;
    if (keyInputs.tavily_api_key) payload.tavily_api_key = keyInputs.tavily_api_key;
    try {
      const res = await updateApiKeys(payload);
      setUser(res.data);
      setKeyInputs({ resend_api_key: '', groq_api_key: '', tavily_api_key: '' });
      setKeysMsg('Saved.');
    } catch (err) {
      setError(getErrorMessage(err, 'Could not save your keys.'));
    } finally {
      setKeysSaving(false);
    }
  };

  const clearKey = async (field) => {
    setKeysSaving(true);
    setError('');
    try {
      const res = await updateApiKeys({ [field]: '' });
      setUser(res.data);
    } catch (err) {
      setError(getErrorMessage(err, 'Could not clear that key.'));
    } finally {
      setKeysSaving(false);
    }
  };

  const toggleBatch = async () => {
    const next = !user.batch_delivery;
    setSaving(true);
    setError('');
    setUser({ ...user, batch_delivery: next });
    try {
      await updatePreferences({ batch_delivery: next });
    } catch (err) {
      setUser({ ...user, batch_delivery: !next });
      setError(getErrorMessage(err, 'Could not save that preference.'));
    } finally {
      setSaving(false);
    }
  };

  const initials = user.name
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  const joined = user.created_at
    ? new Date(user.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })
    : null;

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const closeDeleteModal = () => {
    setShowDeleteModal(false);
    setDeletePassword('');
    setDeleteError('');
  };

  const handleDeleteAccount = async (e) => {
    e.preventDefault();
    setDeleting(true);
    setDeleteError('');
    try {
      await deleteAccount(deletePassword);
      logout();
      navigate('/');
    } catch (err) {
      setDeleteError(getErrorMessage(err, 'Could not delete your account.'));
    } finally {
      setDeleting(false);
    }
  };

  const hasAnyInput = keyInputs.resend_api_key || keyInputs.groq_api_key || keyInputs.tavily_api_key;

  return (
    <div className="page animate-fade" style={{ maxWidth: 640 }}>
      {toast && (
        <div className="toast-container">
          <div className="toast toast-info">
            <Icon name="alertCircle" size={16} /> {toast.message}
          </div>
        </div>
      )}

      <div className="page-header">
        <div className="page-eyebrow">Your Account</div>
        <h1>Profile</h1>
      </div>

      <div className="glass-card profile-hero">
        <div className="profile-avatar">{initials}</div>
        <div>
          <div className="profile-name">{user.name}</div>
          <div className="profile-email">{user.email}</div>
          {joined && <div className="profile-joined">Member since {joined}</div>}
        </div>
      </div>

      {error && (
        <div className="toast toast-error" style={{ position: 'static', marginBottom: 16 }}>{error}</div>
      )}

      <div className="glass-card" style={{ marginBottom: 24 }}>
        <div className="profile-row">
          <div>
            <div className="profile-row-label">Combine deliveries</div>
            <div className="profile-row-hint">
              Topics sharing a delivery time arrive as one email instead of several.
            </div>
          </div>
          <button
            type="button"
            className={`switch ${user.batch_delivery ? 'on' : ''}`}
            onClick={toggleBatch}
            disabled={saving}
            aria-pressed={!!user.batch_delivery}
            aria-label="Combine deliveries"
          >
            <span className="switch-knob" />
          </button>
        </div>
        <div className="profile-row">
          <span className="profile-row-label">Onboarding</span>
          <span className="profile-row-value">{user.is_onboarded ? 'Complete' : 'Incomplete'}</span>
        </div>
        <div className="profile-row">
          <span className="profile-row-label">Email</span>
          <span className="profile-row-value">{user.email}</span>
        </div>
      </div>

      <div
        ref={keysCardRef}
        className={`glass-card api-keys-card ${highlightKeys ? 'highlight' : ''}`}
        style={{ marginBottom: 24 }}
      >
        <div className="api-keys-head">
          <div className="api-keys-icon"><Icon name="key" size={17} /></div>
          <div>
            <div className="profile-row-label">Your Own API Keys</div>
            <div className="profile-row-hint">
              A Groq key powers the AI, a Resend key powers delivery, and a Tavily key powers news
              search — all three are required before you can start a chat. All are free and take
              about a minute each to grab.
            </div>
          </div>
        </div>

        <div className="api-keys-grid">
          {PROVIDERS.map((p) => {
            const isSet = user[p.hasField];
            return (
              <div className={`api-key-card ${p.required && !isSet ? 'needs-attention' : ''}`} key={p.field}>
                {p.field === 'resend_api_key' && !isSet && (
                  <div className="resend-callout">
                    Sign up at Resend with <strong>{user.email}</strong> — the same email you used for ScoutAI — so your free key can send here.
                  </div>
                )}
                <div className="api-key-card-head">
                  <span className="api-key-card-title"><Icon name={p.icon} size={14} /> {p.name}</span>
                  {p.required
                    ? <span className="api-key-badge required">Required</span>
                    : <span className="api-key-badge optional">Optional</span>}
                </div>

                <div className={`api-key-status ${isSet ? 'is-set' : ''}`}>
                  <Icon name={isSet ? 'check' : 'alertCircle'} size={12} />
                  {isSet ? 'Key on file' : 'Not set'}
                </div>

                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    type="password"
                    className="input-field"
                    placeholder={isSet ? '••••••••••••••••' : p.placeholder}
                    value={keyInputs[p.field]}
                    onChange={(e) => setKeyInputs((k) => ({ ...k, [p.field]: e.target.value }))}
                    autoComplete="off"
                  />
                  {isSet && (
                    <button className="btn btn-secondary btn-sm" type="button" disabled={keysSaving} onClick={() => clearKey(p.field)}>Clear</button>
                  )}
                </div>

                <p className="profile-row-hint" style={{ marginTop: 8 }}>
                  {p.blurb} Get one free at <a href={p.getUrl} target="_blank" rel="noreferrer">{p.getLabel}</a>.
                </p>
              </div>
            );
          })}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginTop: 4 }}>
          <button
            className="btn btn-primary btn-sm"
            onClick={saveKeys}
            disabled={keysSaving || !hasAnyInput}
          >
            {keysSaving ? 'Saving...' : 'Save Keys'}
          </button>
          {keysMsg && <span style={{ color: 'var(--accent-ink)', fontSize: 13, fontWeight: 600 }}>{keysMsg}</span>}
        </div>
      </div>

      <button className="btn btn-danger" onClick={handleLogout}>
        <Icon name="logout" size={16} /> Log Out
      </button>

      <div className="glass-card" style={{ marginTop: 24, borderColor: 'rgba(177,67,58,0.25)' }}>
        <div className="profile-row">
          <div>
            <div className="profile-row-label">Delete Account</div>
            <div className="profile-row-hint">
              Permanently deletes your account, topics, and newsletter history. This cannot be undone.
            </div>
          </div>
          <button className="btn btn-danger" onClick={() => setShowDeleteModal(true)}>
            <Icon name="trash" size={16} /> Delete Account
          </button>
        </div>
      </div>

      {showDeleteModal && (
        <div className="modal-overlay" onClick={closeDeleteModal}>
          <div className="glass-card modal animate-fade" onClick={(e) => e.stopPropagation()}>
            <h2>Delete Account</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6, marginBottom: 4 }}>
              <Icon name="alertCircle" size={14} style={{ verticalAlign: -2, marginRight: 4 }} />
              This permanently deletes your account, every topic, and your entire newsletter history.
              There is no way to recover this data afterward.
            </p>
            <form onSubmit={handleDeleteAccount}>
              <div className="input-group">
                <label>Confirm your password</label>
                <input
                  type="password"
                  className="input-field"
                  value={deletePassword}
                  onChange={(e) => setDeletePassword(e.target.value)}
                  autoComplete="current-password"
                  autoFocus
                  required
                />
              </div>

              {deleteError && (
                <div className="toast toast-error" style={{ position: 'static' }}>{deleteError}</div>
              )}

              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={closeDeleteModal} disabled={deleting}>Cancel</button>
                <button type="submit" className="btn btn-danger" disabled={deleting || !deletePassword}>
                  {deleting ? 'Deleting...' : 'Permanently Delete'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
