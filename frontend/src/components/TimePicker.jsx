import { useMemo } from 'react';
import Icon from './Icon';

const HOURS = Array.from({ length: 12 }, (_, i) => i + 1);
const MINUTES = Array.from({ length: 60 }, (_, i) => i);

function from24(value) {
  const [hStr, mStr] = (value || '08:00').split(':');
  const h = parseInt(hStr, 10) || 0;
  const minute = parseInt(mStr, 10) || 0;
  const period = h >= 12 ? 'PM' : 'AM';
  const hour12 = h % 12 === 0 ? 12 : h % 12;
  return { hour12, minute, period };
}

function to24(hour12, minute, period) {
  let h = hour12 % 12;
  if (period === 'PM') h += 12;
  return `${String(h).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
}

/** Replaces the native <input type="time"> OS widget with app-styled dropdowns. */
export default function TimePicker({ value, onChange, autoFocus = false, className = '', onBlur, onKeyDown }) {
  const { hour12, minute, period } = useMemo(() => from24(value), [value]);

  const set = (partial) => {
    onChange(to24(
      partial.hour12 ?? hour12,
      partial.minute ?? minute,
      partial.period ?? period,
    ));
  };

  const handleBlur = (e) => {
    if (onBlur && !e.currentTarget.contains(e.relatedTarget)) onBlur(e);
  };

  return (
    <div className={`time-picker ${className}`} onBlur={handleBlur} onKeyDown={onKeyDown}>
      <Icon name="clock" size={14} className="time-picker-icon" />
      <select
        className="time-picker-select"
        value={hour12}
        autoFocus={autoFocus}
        onChange={(e) => set({ hour12: Number(e.target.value) })}
        aria-label="Hour"
      >
        {HOURS.map((h) => <option key={h} value={h}>{h}</option>)}
      </select>
      <span className="time-picker-sep">:</span>
      <select
        className="time-picker-select"
        value={minute}
        onChange={(e) => set({ minute: Number(e.target.value) })}
        aria-label="Minute"
      >
        {MINUTES.map((m) => <option key={m} value={m}>{String(m).padStart(2, '0')}</option>)}
      </select>
      <select
        className="time-picker-select time-picker-period"
        value={period}
        onChange={(e) => set({ period: e.target.value })}
        aria-label="AM or PM"
      >
        <option value="AM">AM</option>
        <option value="PM">PM</option>
      </select>
    </div>
  );
}
