import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ChatOnboarding from '../components/ChatOnboarding';
import TopicConfirmCard from '../components/TopicConfirmCard';
import Icon from '../components/Icon';
import { createTopic, finishOnboarding, getErrorMessage } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function Onboarding() {
  const [addedTopics, setAddedTopics] = useState([]);
  const [pendingTopic, setPendingTopic] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [leaving, setLeaving] = useState(false);
  const navigate = useNavigate();
  const { setUser, user } = useAuth();

  // Each confirmed topic is created right away, so it shows up on the
  // dashboard immediately instead of waiting for a batch "finish" step.
  const handleAddTopic = async (payload) => {
    setSaving(true);
    setError('');
    try {
      const res = await createTopic(payload);
      setAddedTopics((prev) => [...prev, res.data]);
      setPendingTopic(null);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to add topic. Please try again.'));
    } finally {
      setSaving(false);
    }
  };

  const handleDone = async () => {
    setLeaving(true);
    try {
      if (!user?.is_onboarded) {
        // Topics already exist; this just flips the onboarding flag.
        await finishOnboarding({ topics: [] });
        setUser({ ...user, is_onboarded: true });
      }
      navigate('/dashboard');
    } catch (err) {
      setError(getErrorMessage(err, 'Something went wrong. Please try again.'));
      setLeaving(false);
    }
  };

  return (
    <div className="page animate-fade">
      <div className="page-header" style={{ textAlign: 'center' }}>
        <div className="page-eyebrow" style={{ textAlign: 'center' }}>
          {user?.is_onboarded ? 'Add a Topic' : 'Get Started'}
        </div>
        <h1>{user?.is_onboarded ? 'What else are you following?' : 'Set Up Your News Feed'}</h1>
        <p>One conversation per topic — tell the AI what you want to stay updated on</p>
      </div>

      {error && (
        <div className="toast toast-error" style={{ position: 'static', margin: '0 auto 20px', maxWidth: 520 }}>{error}</div>
      )}

      {addedTopics.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', marginBottom: 24 }}>
          {addedTopics.map((t) => (
            <span key={t.id} className="chip"><Icon name="check" size={12} /> {t.name}</span>
          ))}
        </div>
      )}

      <div className="onboarding-grid">
        <div className="onboarding-panel">
          <h2><Icon name="chat" size={18} /> Chat with AI</h2>
          <ChatOnboarding onTopicReady={setPendingTopic} />
        </div>

        <div className="onboarding-panel">
          <h2><Icon name="check" size={18} /> Confirm &amp; Customize</h2>
          <TopicConfirmCard
            topic={pendingTopic}
            saving={saving}
            onAdd={handleAddTopic}
            onDiscard={() => setPendingTopic(null)}
          />
        </div>
      </div>

      <div className="onboarding-footer">
        <button
          className="btn btn-primary btn-lg"
          onClick={handleDone}
          disabled={leaving || addedTopics.length === 0}
        >
          {leaving ? 'Finishing...' : `Go to Dashboard${addedTopics.length ? ` (${addedTopics.length} added)` : ''}`}
          <Icon name="arrowRight" size={16} />
        </button>
      </div>
    </div>
  );
}
