import { useEffect, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar from './components/Navbar';
import FloatingNav from './components/FloatingNav';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import './index.css';

// Split out of the main bundle: each is only needed once a logged-in user
// navigates there, so a first-time visitor never pays for their JS.
const Onboarding = lazy(() => import('./pages/Onboarding'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const History = lazy(() => import('./pages/History'));
const Profile = lazy(() => import('./pages/Profile'));

const routeFallback = (
  <div className="page" style={{ textAlign: 'center', paddingTop: '100px' }}>
    <div className="typing-indicator" style={{ justifyContent: 'center' }}><div className="typing-dot"></div><div className="typing-dot"></div><div className="typing-dot"></div></div>
  </div>
);

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="page" style={{ textAlign: 'center', paddingTop: '100px' }}><div className="typing-indicator" style={{ justifyContent: 'center' }}><div className="typing-dot"></div><div className="typing-dot"></div><div className="typing-dot"></div></div></div>;
  return user ? children : <Navigate to="/login" />;
}

// The dock (and Navbar links) swap routes via client-side navigation, which
// keeps the browser's scroll position from the previous page. Without this,
// hopping onto /chat from a scrolled-down page lands you in the middle of
// it instead of at the top. Reset on every route change.
function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function AppRoutes() {
  const { user } = useAuth();
  const location = useLocation();
  const showDock = user && user.is_onboarded && location.pathname !== '/';

  return (
    <>
      <ScrollToTop />
      <Navbar />
      <Suspense fallback={routeFallback}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={user ? <Navigate to="/dashboard" /> : <Login />} />
          <Route path="/register" element={user ? <Navigate to="/dashboard" /> : <Register />} />
          <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
          <Route path="/chat" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/history" element={<ProtectedRoute><History /></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </Suspense>
      {showDock && <FloatingNav />}
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
