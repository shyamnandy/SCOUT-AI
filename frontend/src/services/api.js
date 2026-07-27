import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('scoutai_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Extracts a human-readable message from a FastAPI error response.
// `detail` is a string for HTTPException, but an array of
// {type,loc,msg,...} objects for Pydantic 422 validation errors.
export const getErrorMessage = (err, fallback) => {
  const detail = err.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
  return fallback;
};

// Auth
export const registerUser = (data) => api.post('/api/auth/register', data);
export const loginUser = (data) => api.post('/api/auth/login', data);
export const getMe = () => api.get('/api/auth/me');
export const updatePreferences = (data) => api.patch('/api/auth/preferences', data);
export const updateApiKeys = (data) => api.patch('/api/auth/api-keys', data);
export const deleteAccount = (password) => api.delete('/api/auth/me', { data: { password } });

// Chat
export const sendChatMessage = (message) => api.post('/api/chat/onboarding', { message });
export const confirmChatTopic = () => api.post('/api/chat/confirm');
export const finishOnboarding = (data) => api.post('/api/chat/finish', data);
export const resetChatSession = () => api.delete('/api/chat/session');

// Topics
export const getTopics = () => api.get('/api/topics');
export const createTopic = (data) => api.post('/api/topics', data);
export const updateTopic = (id, data) => api.put(`/api/topics/${id}`, data);
export const deleteTopic = (id) => api.delete(`/api/topics/${id}`);
export const toggleTopic = (id) => api.patch(`/api/topics/${id}/toggle`);

// Delivery slots
export const getSlots = () => api.get('/api/slots');
export const addSlot = (time) => api.post('/api/slots', { time });
export const updateSlot = (time, newTime) => api.put(`/api/slots/${time}`, { time: newTime });
export const deleteSlot = (time) => api.delete(`/api/slots/${time}`);

// Newsletters
export const getNewsletters = (params) => api.get('/api/newsletters', { params });
export const getNewsletter = (id) => api.get(`/api/newsletters/${id}`);
export const triggerNewsletter = (topicId) => api.post(`/api/newsletters/trigger/${topicId}`);

export default api;
