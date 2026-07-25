export default function ChatMessage({ message }) {
  const isUser = message.role === 'user';
  return (
    <div className={`chat-bubble ${isUser ? 'user' : 'ai'}`}>
      {message.content}
    </div>
  );
}
