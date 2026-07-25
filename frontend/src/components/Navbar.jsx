import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Navbar() {
  const { user } = useAuth();

  return (
    <nav className="navbar">
      <Link to={user ? '/dashboard' : '/'} className="navbar-brand">
        ScoutAI<span className="dot">.</span>
      </Link>
      {!user && (
        <div className="navbar-links">
          <Link to="/login"><button className="btn btn-secondary btn-sm">Log In</button></Link>
          <Link to="/register"><button className="btn btn-primary btn-sm">Signup</button></Link>
        </div>
      )}
    </nav>
  );
}
