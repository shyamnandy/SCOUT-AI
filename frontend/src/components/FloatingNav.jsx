import { NavLink } from 'react-router-dom';
import Icon from './Icon';

const ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: 'grid' },
  { to: '/chat', label: 'Chat', icon: 'chat' },
  { to: '/profile', label: 'Profile', icon: 'user' },
  { to: '/history', label: 'History', icon: 'archive' },
];

export default function FloatingNav() {
  return (
    <nav className="dock">
      {ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) => `dock-item ${isActive ? 'active' : ''}`}
        >
          <Icon name={item.icon} size={19} strokeWidth={1.6} />
          <span className="dock-label">{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
