import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { DndContext, DragOverlay, useDroppable, MouseSensor, TouchSensor, useSensor, useSensors, pointerWithin } from '@dnd-kit/core';
import TopicCard from '../components/TopicCard';
import TopicForm from '../components/TopicForm';
import TimePicker from '../components/TimePicker';
import Icon from '../components/Icon';
import {
  getTopics, updateTopic, deleteTopic, toggleTopic,
  getSlots, addSlot, updateSlot, deleteSlot, getErrorMessage,
} from '../services/api';
import { useAuth } from '../context/AuthContext';

const formatSlot = (t) => {
  const [h, m] = t.split(':').map(Number);
  const suffix = h < 12 ? 'AM' : 'PM';
  const hour12 = h % 12 === 0 ? 12 : h % 12;
  return `${hour12}:${String(m).padStart(2, '0')} ${suffix}`;
};

/** True once today's occurrence of this HH:MM slot is already behind the clock — the
 * scheduler's 5-min beat (see worker/tasks.py) can't catch it today, so the first
 * delivery would actually land tomorrow. */
const hasSlotPassedToday = (time) => {
  const [h, m] = time.split(':').map(Number);
  const now = new Date();
  const slotToday = new Date(now.getFullYear(), now.getMonth(), now.getDate(), h, m, 0, 0);
  return slotToday <= now;
};

// A drop target — a time slot row, or the pool ('pool'). Its own component
// so each row gets its own useDroppable hook instance regardless of how
// many slots currently exist.
function BoardRow({ dropId, isPool, children }) {
  const { setNodeRef, isOver } = useDroppable({ id: dropId });
  return (
    <div ref={setNodeRef} className={`board-row ${isPool ? 'is-pool' : ''} ${isOver ? 'drag-over' : ''}`}>
      {children}
    </div>
  );
}

export default function Dashboard() {
  const [topics, setTopics] = useState([]);
  const [slots, setSlots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingTopic, setEditingTopic] = useState(null);
  const [activeTopic, setActiveTopic] = useState(null);
  const [newSlotTime, setNewSlotTime] = useState('08:00');
  const [addingSlot, setAddingSlot] = useState(false);
  const [editingSlot, setEditingSlot] = useState(null);
  const [editSlotValue, setEditSlotValue] = useState('');
  const [error, setError] = useState('');
  // A drop onto a slot whose time already passed today — held here instead of
  // committing immediately so the row itself can ask before it's scheduled.
  const [pendingDrop, setPendingDrop] = useState(null);
  // The caution banner's buttons stay inert for a beat after it mounts: the
  // drag overlay vanishes the instant a drop lands (dropAnimation is off), so
  // the trailing native click from that same gesture can land on whatever's
  // now under the pointer — which, without this, would be "Schedule for
  // tomorrow" auto-confirming a drop the user never actually saw the banner for.
  const [dropCautionArmed, setDropCautionArmed] = useState(false);
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!pendingDrop) return;
    setDropCautionArmed(false);
    const timer = setTimeout(() => setDropCautionArmed(true), 350);
    return () => clearTimeout(timer);
  }, [pendingDrop]);

  // Mouse starts dragging after a small move so plain clicks on the card's
  // buttons still register; touch waits for a short hold so a swipe can
  // still scroll the page/track instead of always starting a drag.
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } }),
  );

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

  const handleDragStart = ({ active }) => {
    setActiveTopic(topics.find((t) => t.id === active.data.current?.topicId) || null);
  };

  const handleDragEnd = ({ active, over }) => {
    setActiveTopic(null);
    if (!over) return;
    const topic = topics.find((t) => t.id === active.data.current?.topicId);
    if (!topic) return;

    const targetTime = over.id === 'pool' ? null : over.id;
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

    // Slot time already gone by today — the next beat tick can't catch it,
    // so first delivery will actually be tomorrow. Hold the drop and let the
    // row itself ask, instead of committing right away.
    if (hasSlotPassedToday(targetTime)) {
      setPendingDrop({ topic, time: targetTime, current });
      return;
    }

    setTopicTimes(topic, [...current, targetTime]);
  };

  const handleDragCancel = () => setActiveTopic(null);

  const confirmPendingDrop = () => {
    if (!pendingDrop) return;
    setTopicTimes(pendingDrop.topic, [...pendingDrop.current, pendingDrop.time]);
    setPendingDrop(null);
  };

  const cancelPendingDrop = () => setPendingDrop(null);

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
          dragId={`${keyPrefix}-${t.id}`}
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
    <BoardRow key={key} dropId={key} isPool={isPool}>
      <div className="board-row-head">
        {!isPool && editingSlot === time ? (
          <span className="board-row-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }} onClick={(e) => e.stopPropagation()}>
            <Icon name={icon} size={15} />
            <TimePicker
              className="input-field-sm"
              value={editSlotValue}
              autoFocus
              onChange={setEditSlotValue}
              onBlur={() => handleEditSlot(time)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleEditSlot(time);
                if (e.key === 'Escape') setEditingSlot(null);
              }}
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

      {!isPool && pendingDrop?.time === time && (
        <div className="slot-caution animate-fade">
          <Icon name="alertCircle" size={15} />
          <span><strong>{formatSlot(time)}</strong> already passed today — first delivery would be tomorrow.</span>
          <div className="slot-caution-actions">
            <button className="btn btn-primary btn-sm" onClick={confirmPendingDrop} disabled={!dropCautionArmed}>Schedule for tomorrow</button>
            <button className="btn btn-secondary btn-sm" onClick={cancelPendingDrop} disabled={!dropCautionArmed}>Cancel</button>
          </div>
        </div>
      )}

      {items.length === 0
        ? <p className="board-empty">Drag a topic here to deliver it at this time.</p>
        : renderCards(items, time, key)}
    </BoardRow>
  );

  return (
    <div className="page animate-fade">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <div className="page-eyebrow">Dashboard</div>
          <h1>Your Topics</h1>
          <p>Drag a topic into any number of time slots — use × on a card to remove it from one</p>
        </div>
        {addingSlot ? (
          <div className="add-slot-form">
            <TimePicker value={newSlotTime} onChange={setNewSlotTime} autoFocus />
            <button className="btn btn-primary btn-sm" onClick={handleAddSlot} disabled={!newSlotTime}>Add Slot</button>
            <button className="btn btn-secondary btn-sm" onClick={() => { setAddingSlot(false); setNewSlotTime('08:00'); }}>Cancel</button>
          </div>
        ) : (
          <button className="btn btn-primary" onClick={() => setAddingSlot(true)}>
            <Icon name="plus" size={16} /> Add Time Slot
          </button>
        )}
      </div>

      {error && (
        <div className="toast toast-error" style={{ position: 'static', marginBottom: 20 }}>{error}</div>
      )}

      <div className="stats-bar">
        <div className="glass-card stat-card"><div className="stat-value">{topics.length}</div><div className="stat-label">Total Topics</div></div>
        <div className="glass-card stat-card"><div className="stat-value">{scheduled}</div><div className="stat-label">Scheduled</div></div>
        <div className="glass-card stat-card"><div className="stat-value">{pooledCount}</div><div className="stat-label">In Pool</div></div>
      </div>

      {/* pointerWithin: the row the pointer/finger is literally over wins,
          rather than whichever row the card's full ghost rect overlaps most —
          more predictable, especially on touch where a finger hides the
          exact point. autoScroll speed ramps from 0 at the threshold edge up
          to `acceleration` px/tick right at the viewport edge (library
          default is 10; 12 is a mild bump, not a runaway one). */}
      <DndContext
        sensors={sensors}
        collisionDetection={pointerWithin}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
        autoScroll={{ acceleration: 12 }}
      >
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
          </div>

          <aside className="board-pool">
            <BoardRow dropId="pool" isPool>
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
            </BoardRow>
          </aside>
        </div>

        {/* Portaled to <body> by dnd-kit — the ghost that actually follows the
            pointer, immune to the board-track/pool's own scroll clipping.
            dropAnimation is off: dnd-kit's default snap-back animation looks
            up the dragged card's DOM node by its *original* id afterward, but
            a topic scheduled into several slots at once keeps that old id
            mounted elsewhere on the board — so the default animation can
            scroll the page back to that other slot right after a drop. */}
        <DragOverlay dropAnimation={null}>
          {activeTopic && (
            <TopicCard
              topic={activeTopic}
              dragId="drag-overlay-preview"
              isOverlay
              onEdit={() => {}}
              onDelete={() => {}}
              onToggle={() => {}}
              onUnschedule={() => {}}
            />
          )}
        </DragOverlay>
      </DndContext>

      {topics.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon"><Icon name="inbox" size={24} /></div>
          <h3>No Topics Yet</h3>
          <p>Chat with the AI to create your first topic and start receiving curated newsletters</p>
          <button className="btn btn-primary" onClick={() => navigate('/chat')}>
            <Icon name="chat" size={16} /> Start a Chat
          </button>
        </div>
      )}

      {editingTopic && <TopicForm topic={editingTopic} onSubmit={handleUpdate} onClose={() => setEditingTopic(null)} />}
    </div>
  );
}
