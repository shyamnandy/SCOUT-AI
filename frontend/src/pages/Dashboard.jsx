import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import TopicCard from '../components/TopicCard';
import TopicForm from '../components/TopicForm';
import Icon from '../components/Icon';
import {
  getTopics, createTopic, updateTopic, deleteTopic, toggleTopic,
  getSlots, addSlot, updateSlot, deleteSlot, getErrorMessage,
} from '../services/api';
import { useAuth } from '../context/AuthContext';

const formatSlot = (t) => {
  const [h, m] = t.split(':').map(Number);
  const suffix = h < 12 ? 'AM' : 'PM';
  const hour12 = h % 12 === 0 ? 12 : h % 12;
  return `${hour12}:${String(m).padStart(2, '0')} ${suffix}`;
};

export default function Dashboard() {
  const [topics, setTopics] = useState([]);
  const [slots, setSlots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingTopic, setEditingTopic] = useState(null);
  const [dragOver, setDragOver] = useState(null);
  const [newSlotTime, setNewSlotTime] = useState('');
  const [addingSlot, setAddingSlot] = useState(false);
  const [editingSlot, setEditingSlot] = useState(null);
  const [editSlotValue, setEditSlotValue] = useState('');
  const [error, setError] = useState('');
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user && !user.is_onboarded) { navigate('/onboarding'); return; }
    fetchAll();
  }, [user]);

  const fetchAll = async () => {
    try {
      const [tRes, sRes] = await Promise.all([getTopics(), getSlots()]);
      setTopics(tRes.data);
      setSlots(sRes.data);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load your board.'));
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (data) => {
    await createTopic(data);
    setShowForm(false);
    fetchAll();
  };

  const handleUpdate = async (data) => {
    await updateTopic(editingTopic.id, data);
    setEditingTopic(null);
    fetchAll();
  };

  const handleDelete = async (id) => {
    if (!confirm('Delete this topic?')) return;
    await deleteTopic(id);
    fetchAll();
  };

  /** Pausing drops a topic into the pool; resuming returns it to its slots. */
  const handleToggle = async (id) => {
    setTopics((prev) => prev.map((t) => (t.id === id ? { ...t, is_active: !t.is_active } : t)));
    try {
      await toggleTopic(id);
    } catch (err) {
      setError(getErrorMessage(err, 'Could not change that topic.'));
      fetchAll();
    }
  };

  /** Persist a topic's new set of delivery times, with optimistic UI. */
  const setTopicTimes = async (topic, times) => {
    const next = [...new Set(times)].sort();
    setTopics((prev) => prev.map((t) => (t.id === topic.id ? { ...t, delivery_times: next } : t)));
    try {
      await updateTopic(topic.id, { delivery_times: next });
    } catch (err) {
      setError(getErrorMessage(err, 'Could not update the schedule.'));
      fetchAll();
    }
  };

  const handleDrop = (e, targetTime) => {
    e.preventDefault();
    setDragOver(null);
    let payload;
    try {
      payload = JSON.parse(e.dataTransfer.getData('application/json'));
    } catch {
      return;
    }
    const topic = topics.find((t) => t.id === payload.id);
    if (!topic) return;

    const current = topic.delivery_times || [];

    if (targetTime === null) {
      // Dropped on the pool: unschedule from every slot.
      if (!current.length) return;
      setTopicTimes(topic, []);
      return;
    }

    // Dropping onto a slot always ADDS it — a topic can live in several
    // slots at once. Removing is explicit: the card's × or a drop on the pool.
    if (current.includes(targetTime)) return;
    setTopicTimes(topic, [...current, targetTime]);
  };

  const handleUnschedule = (topic, time) => {
    setTopicTimes(topic, (topic.delivery_times || []).filter((t) => t !== time));
  };

  const handleAddSlot = async () => {
    if (!newSlotTime) return;
    try {
      const res = await addSlot(newSlotTime);
      setSlots(res.data);
      setNewSlotTime('');
      setAddingSlot(false);
    } catch (err) {
      setError(getErrorMessage(err, 'Could not add that slot.'));
    }
  };

  const handleEditSlot = async (time) => {
    if (!editSlotValue || editSlotValue === time) {
      setEditingSlot(null);
      return;
    }
    try {
      const res = await updateSlot(time, editSlotValue);
      setSlots(res.data);
      setEditingSlot(null);
      fetchAll();
    } catch (err) {
      setError(getErrorMessage(err, 'Could not update that slot.'));
      setEditingSlot(null);
    }
  };

  const handleDeleteSlot = async (time) => {
    const count = topics.filter((t) => (t.delivery_times || []).includes(time)).length;
    const msg = count
      ? `Remove the ${formatSlot(time)} slot? ${count} topic${count === 1 ? '' : 's'} will move back to the pool.`
      : `Remove the ${formatSlot(time)} slot?`;
    if (!confirm(msg)) return;
    try {
      const res = await deleteSlot(time);
      setSlots(res.data);
      fetchAll();
    } catch (err) {
      setError(getErrorMessage(err, 'Could not remove that slot.'));
    }
  };

  // A topic sits in the pool when it's paused or has no delivery time yet.
  // Unscheduled wins when both apply, so a topic never shows up twice.
  const unscheduled = topics.filter((t) => !(t.delivery_times || []).length);
  const paused = topics.filter((t) => t.is_active === false && (t.delivery_times || []).length);
  const pooledCount = unscheduled.length + paused.length;
  const scheduled = topics.length - pooledCount;

  if (loading) {
    return (
      <div className="page" style={{ textAlign: 'center', paddingTop: 80 }}>
        <p style={{ color: 'var(--text-muted)' }}>Loading your board...</p>
      </div>
    );
  }

  const renderCards = (items, fromTime, keyPrefix, className = 'board-track') => (
    <div className={className}>
      {items.map((t) => (
        <TopicCard
          key={`${keyPrefix}-${t.id}`}
          topic={t}
          fromTime={fromTime}
          onEdit={setEditingTopic}
          onDelete={handleDelete}
          onToggle={handleToggle}
          onUnschedule={handleUnschedule}
        />
      ))}
    </div>
  );

  const renderRow = ({ key, time, title, icon, items, isPool }) => (
    <div
      key={key}
      className={`board-row ${isPool ? 'is-pool' : ''} ${dragOver === key ? 'drag-over' : ''}`}
      onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = isPool ? 'move' : 'copy';
        setDragOver(key);
      }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setDragOver(null); }}
      onDrop={(e) => handleDrop(e, time)}
    >
      <div className="board-row-head">
        {!isPool && editingSlot === time ? (
          <span className="board-row-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Icon name={icon} size={15} />
            <input
              type="time"
              className="input-field input-field-sm"
              value={editSlotValue}
              autoFocus
              onChange={(e) => setEditSlotValue(e.target.value)}
              onBlur={() => handleEditSlot(time)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleEditSlot(time);
                if (e.key === 'Escape') setEditingSlot(null);
              }}
              onClick={(e) => e.stopPropagation()}
            />
          </span>
        ) : (
          <span
            className={`board-row-title ${!isPool ? 'is-editable' : ''}`}
            title={!isPool ? 'Click to change the time' : undefined}
            onClick={() => {
              if (isPool) return;
              setEditingSlot(time);
              setEditSlotValue(time);
            }}
          >
            <Icon name={icon} size={15} /> {title}
          </span>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="board-row-count">{items.length}</span>
          {!isPool && (
            <button className="icon-btn danger" title="Remove slot" onClick={() => handleDeleteSlot(time)}>
              <Icon name="trash" size={13} />
            </button>
          )}
        </div>
      </div>

      {items.length === 0
        ? <p className="board-empty">Drag a topic here to deliver it at this time.</p>
        : renderCards(items, time, key)}
    </div>
  );

  return (
    <div className="page animate-fade">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <div className="page-eyebrow">Dashboard</div>
          <h1>Your Topics</h1>
          <p>Drag a topic into any number of time slots — use × on a card to remove it from one</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(true)}>
          <Icon name="plus" size={16} /> New Topic
        </button>
      </div>

      {error && (
        <div className="toast toast-error" style={{ position: 'static', marginBottom: 20 }}>{error}</div>
      )}

      <div className="stats-bar">
        <div className="glass-card stat-card"><div className="stat-value">{topics.length}</div><div className="stat-label">Total Topics</div></div>
        <div className="glass-card stat-card"><div className="stat-value">{scheduled}</div><div className="stat-label">Scheduled</div></div>
        <div className="glass-card stat-card"><div className="stat-value">{pooledCount}</div><div className="stat-label">In Pool</div></div>
      </div>

      <div className="board-layout">
        <div className="board-rows">
          {slots.map((time) =>
            renderRow({
              key: time,
              time,
              title: formatSlot(time),
              icon: 'clock',
              // Paused topics live in the pool, not in their slots.
              items: topics.filter((t) => t.is_active && (t.delivery_times || []).includes(time)),
              isPool: false,
            })
          )}

          <div className="board-row board-row-add">
            {addingSlot ? (
              <div className="add-slot-form">
                <input
                  type="time"
                  className="input-field"
                  value={newSlotTime}
                  onChange={(e) => setNewSlotTime(e.target.value)}
                  autoFocus
                />
                <button className="btn btn-primary btn-sm" onClick={handleAddSlot} disabled={!newSlotTime}>Add Slot</button>
                <button className="btn btn-secondary btn-sm" onClick={() => { setAddingSlot(false); setNewSlotTime(''); }}>Cancel</button>
              </div>
            ) : (
              <button className="add-slot-btn" onClick={() => setAddingSlot(true)}>
                <Icon name="plus" size={16} /> <span>New Time Slot</span>
              </button>
            )}
          </div>
        </div>

        <aside className="board-pool">
          <div
            className={`board-row is-pool ${dragOver === 'pool' ? 'drag-over' : ''}`}
            onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; setDragOver('pool'); }}
            onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setDragOver(null); }}
            onDrop={(e) => handleDrop(e, null)}
          >
            <div className="board-row-head">
              <span className="board-row-title"><Icon name="inbox" size={15} /> Topic Pool</span>
              <span className="board-row-count">{pooledCount}</span>
            </div>

            <div className="pool-scroll">
              <div className="pool-partitions">
                <div className="pool-partition">
                  <div className="pool-partition-head">
                    <span>Unscheduled</span>
                    <span className="board-row-count">{unscheduled.length}</span>
                  </div>
                  {unscheduled.length === 0
                    ? <p className="board-empty">No unscheduled topics.</p>
                    : renderCards(unscheduled, null, 'unsched', 'pool-list')}
                </div>

                <div className="pool-partition">
                  <div className="pool-partition-head">
                    <span>Paused</span>
                    <span className="board-row-count">{paused.length}</span>
                  </div>
                  {paused.length === 0
                    ? <p className="board-empty">Nothing paused.</p>
                    : renderCards(paused, null, 'paused', 'pool-list')}
                </div>
              </div>
            </div>
          </div>
        </aside>
      </div>

      {topics.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon"><Icon name="inbox" size={24} /></div>
          <h3>No Topics Yet</h3>
          <p>Create your first topic to start receiving curated newsletters</p>
          <button className="btn btn-primary" onClick={() => setShowForm(true)}>
            <Icon name="plus" size={16} /> Create Topic
          </button>
        </div>
      )}

      {showForm && <TopicForm onSubmit={handleCreate} onClose={() => setShowForm(false)} />}
      {editingTopic && <TopicForm topic={editingTopic} onSubmit={handleUpdate} onClose={() => setEditingTopic(null)} />}
    </div>
  );
}
