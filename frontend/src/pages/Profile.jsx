import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { updatePreferences, getErrorMessage } from '../services/api';
import Icon from '../components/Icon';

export default function Profile() {
  const { user, setUser, logout } = useAuth();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  if (!user) return null;

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

  return (
    <div className="page animate-fade" style={{ maxWidth: 640 }}>
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

      <button className="btn btn-danger" onClick={handleLogout}>
        <Icon name="logout" size={16} /> Log Out
      </button>
    </div>
  );
}
