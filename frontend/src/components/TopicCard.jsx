import { useDraggable } from '@dnd-kit/core';
import Icon from './Icon';

/**
 * Full topic card, draggable between the pool and time-slot rows.
 * `fromTime` is set when the card is rendered inside a slot row.
 * `dragId` must be unique among *currently mounted* cards — a topic
 * scheduled into several slots at once renders one card per slot
 * simultaneously, so `topic.id` alone can collide.
 * `isOverlay` renders the static ghost clone shown in the DragOverlay —
 * visual only, never itself grabbable.
 */
export default function TopicCard({ topic, dragId, fromTime = null, isOverlay = false, onEdit, onDelete, onToggle, onUnschedule }) {
  const isExpired =
    topic.lifecycle === 'ephemeral' &&
    topic.expiration_date &&
    new Date(topic.expiration_date) < new Date();
  const needsDate = topic.lifecycle === 'ephemeral' && !topic.expiration_date;
  const isUnscheduled = !(topic.delivery_times || []).length;

  let statusClass = 'active';
  let statusText = 'Active';
  if (isExpired) {
    statusClass = 'expired';
    statusText = 'Expired';
  } else if (!topic.is_active) {
    statusClass = 'paused';
    statusText = 'Paused';
  } else if (needsDate) {
    statusClass = 'paused';
    statusText = 'Needs End Date';
  } else if (isUnscheduled) {
    statusClass = 'paused';
    statusText = 'Unscheduled';
  }

  // The card itself never moves — it just dims to mark the drag source.
  // A <DragOverlay> (rendered once in Dashboard) is what actually follows
  // the pointer, portaled to <body> so it isn't clipped by the scrollable
  // track/pool it started in and always paints above every row.
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: dragId,
    data: { topicId: topic.id },
    disabled: isOverlay,
  });

  return (
    <div
      ref={setNodeRef}
      className={`glass-card topic-card ${isExpired ? 'is-expired' : ''} ${isDragging ? 'is-dragging' : ''} ${isOverlay ? 'is-overlay' : ''}`}
      data-category={topic.category}
      {...listeners}
      {...attributes}
    >
      <div className="topic-card-header">
        <div>
          <span className={`status-dot ${statusClass}`}></span>
          <span className="topic-card-status">{statusText}</span>
        </div>
        <div className="topic-card-actions">
          {fromTime && (
            <button className="btn btn-secondary btn-icon" title="Remove from this slot" onClick={() => onUnschedule(topic, fromTime)}>
              <Icon name="close" size={14} />
            </button>
          )}
          <button
            className="btn btn-secondary btn-icon"
            title={topic.is_active ? 'Pause (moves to pool)' : 'Resume'}
            onClick={() => onToggle(topic.id)}
          >
            <Icon name={topic.is_active ? 'pause' : 'play'} size={14} />
          </button>
          <button className="btn btn-secondary btn-icon" title="Edit" onClick={() => onEdit(topic)}>
            <Icon name="edit" size={14} />
          </button>
          <button className="btn btn-danger btn-icon" title="Delete" onClick={() => onDelete(topic.id)}>
            <Icon name="trash" size={14} />
          </button>
        </div>
      </div>

      <h3 className="topic-card-title">{topic.name}</h3>

      <div className="topic-keywords">
        {topic.keywords.slice(0, 5).map((kw) => (<span key={kw} className="chip">{kw}</span>))}
        {topic.keywords.length > 5 && <span className="chip">+{topic.keywords.length - 5}</span>}
      </div>

      <div className="topic-meta">
        <div className="topic-meta-item">
          <Icon name="clock" size={13} />
          {isUnscheduled ? 'No delivery time set' : topic.delivery_times.join(', ')}
        </div>
        <div className="topic-meta-item">
          <Icon name={topic.lifecycle === 'perpetual' ? 'infinity' : 'calendar'} size={13} />
          {topic.lifecycle === 'perpetual'
            ? 'Perpetual'
            : topic.expiration_date
              ? `Until ${new Date(topic.expiration_date).toLocaleDateString()}`
              : 'End date not set'}
        </div>
        {topic.last_delivered_at && (
          <div className="topic-meta-item">
            <Icon name="mail" size={13} /> Last: {new Date(topic.last_delivered_at).toLocaleString()}
          </div>
        )}
      </div>
    </div>
  );
}
