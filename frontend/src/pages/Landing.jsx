import { Link } from 'react-router-dom';
import Icon from '../components/Icon';
import { useAuth } from '../context/AuthContext';

const today = new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

const FEATURES = [
  { icon: 'chat', title: 'Chat Your Interests', desc: 'Tell our AI what you care about in plain language, or pick from curated categories. It asks smart follow-up questions to nail your exact preferences.' },
  { icon: 'clock', title: 'Set Your Schedule', desc: 'Choose delivery times for each topic independently. Morning AI news, evening sports updates — your call.' },
  { icon: 'calendar', title: 'Expiration Control', desc: 'Set topics to run forever or auto-expire after an event ends. World Cup over? Auto-unsubscribe.' },
  { icon: 'grid', title: '6 Trusted Sources', desc: 'Our AI scouts the internet, selects 6 legitimate sources, scrapes the full content, and discards all the noise.' },
  { icon: 'archive', title: 'AI Analysis', desc: 'Each article is scored for relevance, filtered for quality, and summarized into clean 2-3 sentence blurbs.' },
  { icon: 'mail', title: 'Auto-Delivered', desc: 'A beautiful, curated newsletter lands in your inbox automatically. Zero effort. Pure signal.' },
];

export default function Landing() {
  const { user } = useAuth();

  return (
    <>
      <section className="hero">
        <div className="hero-inner">
          <div className="animate-fade">
            <div className="hero-eyebrow">{today}</div>
            <h1>
              Stop scrolling.<br />
              Start <em>knowing.</em>
            </h1>
            <p>
              ScoutAI curates personalized newsletters from 6 trusted sources — delivered to your inbox on your schedule. AI-powered. Zero noise.
            </p>
            <div className="hero-cta">
              {user ? (
                <Link to="/dashboard"><button className="btn btn-primary btn-lg">Go to Dashboard <Icon name="arrowRight" size={16} /></button></Link>
              ) : (
                <>
                  <Link to="/register"><button className="btn btn-primary btn-lg">Start Free <Icon name="arrowRight" size={16} /></button></Link>
                  <Link to="/login"><button className="btn btn-secondary btn-lg">Sign In</button></Link>
                </>
              )}
            </div>
          </div>

          <div className="glass-card hero-card animate-slide" style={{ animationDelay: '0.15s' }}>
            <span className="ribbon">Topic #2481</span>
            <div className="hero-card-header">
              <div className="hero-card-avatar">AI</div>
              <div>
                <div className="hero-card-name">AI Product Launches</div>
                <div className="hero-card-meta">Delivered daily, 8:00 AM</div>
              </div>
            </div>
            <p className="hero-card-quote">
              "Three funded startups launched competing AI agents this week, and one major lab shipped a new reasoning model."
            </p>
            <div className="hero-card-footer">
              <div>
                <div className="hero-card-footer-label">Sources</div>
                <div className="hero-card-footer-value">6 curated</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className="hero-card-footer-label">Next delivery</div>
                <div className="hero-card-footer-value" style={{ color: 'var(--accent-ink)' }}>Tomorrow, 8:00 AM</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="features-section">
        <h2 className="animate-fade">How It Works</h2>
        <p className="section-sub">A quiet, focused pipeline between the noise of the internet and your inbox.</p>
        <div className="features-grid">
          {FEATURES.map((f, i) => (
            <div key={i} className="glass-card feature-card animate-slide" style={{ animationDelay: `${i * 0.08}s` }}>
              <div className="feature-icon"><Icon name={f.icon} size={19} /></div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
