import { useState } from 'react';
import ChatOnboarding from '../components/ChatOnboarding';
import TopicConfirmCard from '../components/TopicConfirmCard';
import Icon from '../components/Icon';
import { createTopic, getErrorMessage } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function Onboarding() {
  const [addedTopics, setAddedTopics] = useState([]);
  const [pendingTopic, setPendingTopic] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const { setUser, user } = useAuth();

  // Each confirmed topic is created right away, so it shows up on the
  // dashboard immediately instead of waiting for a batch "finish" step.
  // The backend flips is_onboarded the moment a topic exists, so there's
  // no separate "complete onboarding" call — mirror that here so a user
  // who navigates away any other way (not just this button) is never
  // left stuck being redirected back to onboarding.
  const handleAddTopic = async (payload) => {
    setSaving(true);
    setError('');
    try {
      const res = await createTopic(payload);
      setAddedTopics((prev) => [...prev, res.data]);
      setPendingTopic(null);
      if (!user.is_onboarded) setUser({ ...user, is_onboarded: true });
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to add topic. Please try again.'));
    } finally {
      setSaving(false);
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
          <ChatOnboarding onTopicReady={setPendingTopic} locked={!user?.has_groq_key} />
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
    </div>
  );
}
