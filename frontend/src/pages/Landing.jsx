import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Icon from '../components/Icon';
import { useAuth } from '../context/AuthContext';

const today = new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

const HERO_TOPICS = [
  { ribbon: 'Topic #2481', name: 'AI Product Launches', meta: 'Delivered daily, 8:00 AM', quote: 'I want to follow AI product launches — new models, tools, and startup releases, not academic research papers.', next: 'Tomorrow, 8:00 AM' },
  { ribbon: 'Topic #3312', name: 'Backend & Cloud Infra', meta: 'Delivered daily, 7:00 AM', quote: 'Track software dev news for me, focused on backend and cloud infra — things like new framework releases and major outages.', next: 'Tomorrow, 7:00 AM' },
  { ribbon: 'Topic #5091', name: 'Premier League Football', meta: 'Delivered daily, 9:00 PM', quote: 'I want Premier League football news, especially match results and player performance — skip transfer rumors.', next: 'Tonight, 9:00 PM' },
  { ribbon: 'Topic #2755', name: 'US Tech Stocks & Fed Watch', meta: 'Delivered daily, 6:00 AM', quote: 'Follow stock market news for me, specifically US tech stocks and Fed rate decisions.', next: 'Tomorrow, 6:00 AM' },
  { ribbon: 'Topic #4108', name: 'Crypto — BTC & ETH', meta: 'Delivered daily, 7:00 AM', quote: 'I want crypto news — Bitcoin and Ethereum price movements and regulatory news, not meme coins.', next: 'Tomorrow, 7:00 AM' },
  { ribbon: 'Topic #1943', name: 'AI Research', meta: 'Delivered weekly, Mon 9:00 AM', quote: 'Follow AI research news for me, as a CS student — new papers and breakthroughs I can actually use, not corporate PR.', next: 'Monday, 9:00 AM' },
  { ribbon: 'Topic #4420', name: 'Middle East Conflict & Politics', meta: 'Delivered daily, 7:00 AM', quote: 'I want world news on the Middle East — major political and conflict developments only.', next: 'Tomorrow, 7:00 AM' },
  { ribbon: 'Topic #3319', name: 'Marvel & DC Universe', meta: 'Delivered weekly, Fri 6:00 PM', quote: 'Track entertainment news for me — new Marvel/DC movie and show announcements.', next: 'Friday, 6:00 PM' },
  { ribbon: 'Topic #5502', name: 'FIFA World Cup 2026', meta: 'Delivered daily · Expires Dec 2026', quote: 'I want World Cup news until the tournament ends in December — match highlights and standings.', next: 'Tomorrow, 8:00 AM' },
  { ribbon: 'Topic #3867', name: 'Personal Finance Basics', meta: 'Delivered weekly, Sun 9:00 AM', quote: 'Follow personal finance news for me — practical tips on saving and investing, explained simply, not macro-economic theory.', next: 'Sunday, 9:00 AM' },
];

const FEATURES = [
  { icon: 'chat', title: 'Chat Your Interests', desc: 'Tell our AI what you want to follow, in plain language — no forms, no keyword picker. It asks 1-2 quick follow-up questions to nail your exact focus.' },
  { icon: 'clock', title: 'Set Your Schedule', desc: 'Choose delivery times for each topic independently. Morning AI news, evening sports updates — your call.' },
  { icon: 'calendar', title: 'Expiration Control', desc: 'Set topics to run forever or auto-expire after an event ends. World Cup over? Auto-unsubscribed, no cleanup needed.' },
  { icon: 'grid', title: 'Credible Sources Only', desc: 'Our AI searches broadly, scores every candidate for credibility and relevance, and keeps one article per real story — no duplicate coverage, no content farms.' },
  { icon: 'archive', title: 'AI Analysis', desc: 'Each article is scored for relevance and importance, then summarized into a clean 2-3 sentence blurb.' },
  { icon: 'mail', title: 'Auto-Delivered', desc: 'A curated newsletter lands in your inbox automatically, on schedule. Zero effort. Pure signal.' },
];

const TYPE_SPEED_MS = 22;
const HOLD_MS = 1500;

export default function Landing() {
  const { user } = useAuth();
  const [topicIndex, setTopicIndex] = useState(0);
  const [typed, setTyped] = useState('');

  const topic = HERO_TOPICS[topicIndex];

  useEffect(() => {
    let i = 0;
    let holdTimer;
    setTyped('');
    const typeTimer = setInterval(() => {
      i += 1;
      setTyped(topic.quote.slice(0, i));
      if (i >= topic.quote.length) {
        clearInterval(typeTimer);
        holdTimer = setTimeout(() => {
          setTopicIndex((idx) => (idx + 1) % HERO_TOPICS.length);
        }, HOLD_MS);
      }
    }, TYPE_SPEED_MS);
    return () => { clearInterval(typeTimer); clearTimeout(holdTimer); };
  }, [topicIndex]);

  return (
    <>
      <section className="hero">
        <div className="hero-inner">
          <div className="animate-fade">
            <div className="hero-eyebrow">{today}</div>
            <h1>
              It's not a newsletter.<br />
              It's autopilot for your <em>curiosity.</em>
            </h1>
            <p>
              Tell ScoutAI what you want to stay updated on — once. It searches, curates from 6 trusted sources, and delivers straight to your inbox on the schedule you set. No app to check. No search to repeat.
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
            <span className="ribbon">{topic.ribbon}</span>
            <div className="hero-card-header">
              <div className="hero-card-avatar">AI</div>
              <div>
                <div className="hero-card-name">{topic.name}</div>
                <div className="hero-card-meta">{topic.meta}</div>
              </div>
            </div>
            <p className="hero-card-quote">
              "{typed}<span className="typing-cursor" />{typed.length >= topic.quote.length ? '"' : ''}
            </p>
            <div className="hero-card-footer">
              <div>
                <div className="hero-card-footer-label">Next delivery</div>
                <div className="hero-card-footer-value" style={{ color: 'var(--accent-ink)' }}>{topic.next}</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="problem-section">
        <div className="problem-inner">
          <div className="page-eyebrow">The Problem</div>
          <h2>You've checked the same thing three times this week.</h2>
          <p className="section-sub">
            The score. The price. The story everyone's talking about. You didn't forget to
            care — you just don't have someone whose only job is checking for you.
          </p>
          <div className="repeat-row">
            <span className="repeat-chip">"Did the match end?"</span>
            <span className="repeat-chip">"Is the price down yet?"</span>
            <span className="repeat-chip">"Any update on—"</span>
            <span className="repeat-chip">"Wait, did I miss it?"</span>
          </div>
        </div>
      </section>

      <section className="features-section">
        <h2 className="animate-fade">How It Works</h2>
        <p className="section-sub">A quiet, focused pipeline between the noise of the internet and your inbox.</p>
        <div className="features-grid">
          {FEATURES.map((f, i) => (
            <div key={i} className="glass-card feature-card animate-slide" style={{ animationDelay: `${i * 0.08}s` }}>
              <h3><Icon name={f.icon} size={16} /> {f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="pricing-section">
        <div className="glass-card pricing-card">
          <h2>No subscription. Ever.</h2>
          <span className="time-tag">Hardly takes 2 <Icon name="clock" size={11} /> minutes</span>
          <p>
            ScoutAI itself is 100% free. But it isn't free to run — it needs your own API
            keys to work, not ours. <strong>Before you can create a topic, you must sign up
            for a free account on both platforms below and paste your key into your ScoutAI
            profile.</strong> There's no way around this step — no keys, no newsletter.
          </p>
          <div className="platform-row">
            <a className="platform-badge" href="https://console.groq.com/keys" target="_blank" rel="noopener noreferrer">
              <img src="/groq-mark.svg" alt="" width="30" height="30" />
              <span className="platform-badge-text">
                <strong>Groq</strong>
                <em>Powers the AI &amp; chat</em>
              </span>
              <span className="api-key-badge required">Required</span>
            </a>
            <a className="platform-badge" href="https://resend.com/api-keys" target="_blank" rel="noopener noreferrer">
              <img src="/resend-mark.svg" alt="" width="26" height="26" />
              <span className="platform-badge-text">
                <strong>Resend</strong>
                <em>Sends your newsletter</em>
              </span>
              <span className="api-key-badge required">Required</span>
            </a>
          </div>
          <div className="pricing-steps">
            <div><strong>1</strong> Create a free account with Groq and Resend</div>
            <div><strong>2</strong> Paste both keys into your ScoutAI profile, once</div>
            <div><strong>3</strong> Never think about billing again — you're always in control of the cost</div>
          </div>
        </div>
      </section>

      <section className="closing-cta">
        <h2>Put your curiosity on autopilot.</h2>
        <p>One conversation. Zero repeat searches.</p>
        {user ? (
          <Link to="/dashboard"><button className="btn btn-primary btn-lg">Go to Dashboard <Icon name="arrowRight" size={16} /></button></Link>
        ) : (
          <Link to="/register"><button className="btn btn-primary btn-lg">Start Free <Icon name="arrowRight" size={16} /></button></Link>
        )}
      </section>

      <footer className="site-footer">
        <span className="footer-brand">ScoutAI<span className="dot">.</span></span>
        <span className="footer-copy">&copy; {new Date().getFullYear()} ScoutAI — built for people tired of asking twice.</span>
      </footer>
    </>
  );
}
