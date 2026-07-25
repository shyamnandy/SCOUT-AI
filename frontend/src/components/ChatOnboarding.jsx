import { useState, useRef, useEffect } from 'react';
import ChatMessage from './ChatMessage';
import Icon from './Icon';
import { sendChatMessage, confirmChatTopic, resetChatSession, getErrorMessage } from '../services/api';

const GREETING = { role: 'assistant', content: "Hey there — I'm your ScoutAI assistant. Tell me what topic or area you want to stay updated on: a technology, a sports league, a financial market, a world event..." };

export default function ChatOnboarding({ onTopicReady }) {
  const [messages, setMessages] = useState([GREETING]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [awaitingConfirmation, setAwaitingConfirmation] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, awaitingConfirmation]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput('');
    setAwaitingConfirmation(false);
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      const res = await sendChatMessage(userMsg);
      setMessages((prev) => [...prev, { role: 'assistant', content: res.data.reply }]);
      setAwaitingConfirmation(res.data.awaiting_confirmation);
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', content: getErrorMessage(err, "Sorry, I had trouble processing that. Could you try again?") }]);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    setConfirming(true);
    try {
      const res = await confirmChatTopic();
      if (res.data.topic) {
        onTopicReady(res.data.topic);
      }
      await resetChatSession();
      setMessages([GREETING]);
      setAwaitingConfirmation(false);
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', content: getErrorMessage(err, "Couldn't confirm that topic — try again?") }]);
    } finally {
      setConfirming(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="glass-card chat-container">
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}
        {loading && (
          <div className="typing-indicator" style={{ alignSelf: 'flex-start' }}>
            <div className="typing-dot"></div>
            <div className="typing-dot"></div>
            <div className="typing-dot"></div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {awaitingConfirmation && (
        <div className="chat-confirm-row">
          <button className="btn btn-primary btn-sm" onClick={handleConfirm} disabled={confirming}>
            <Icon name="check" size={14} /> {confirming ? 'Confirming...' : 'Confirm Topic'}
          </button>
          <span className="hint">or just tell me what to change</span>
        </div>
      )}

      <div className="chat-input-bar">
        <input
          type="text"
          className="input-field"
          placeholder="Tell me what interests you..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading || confirming}
        />
        <button className="btn btn-primary btn-icon" onClick={handleSend} disabled={loading || confirming || !input.trim()}>
          <Icon name="send" size={16} />
        </button>
      </div>
    </div>
  );
}
