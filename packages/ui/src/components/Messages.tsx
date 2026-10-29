import { useState } from 'react';
import { PageLayout } from './PageLayout';
import { MESSAGE_THREADS } from '../data/seed';
import type { MessageThread } from '../data/seed';

function timeAgo(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return 'Just now';
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'Yesterday';
  return `${days}d ago`;
}

function ThreadItem({
  thread,
  isSelected,
  onClick,
}: {
  thread: MessageThread;
  isSelected: boolean;
  onClick: () => void;
}) {
  const lastMessage = thread.messages[thread.messages.length - 1];
  const initial = thread.clientName.charAt(0);

  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-4 transition-colors ${
        isSelected
          ? 'bg-blue-50 border-l-4 border-blue-500'
          : 'hover:bg-gray-50 border-l-4 border-transparent'
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
          {initial}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex justify-between items-baseline">
            <p className="font-medium text-sm text-gray-900 truncate">
              {thread.clientName}
            </p>
            <span className="text-xs text-gray-400 flex-shrink-0 ml-2">
              {timeAgo(lastMessage.timestamp)}
            </span>
          </div>
          <p className="text-xs text-gray-500 truncate mt-0.5">
            {lastMessage.from === 'advisor' ? 'You: ' : ''}
            {lastMessage.text}
          </p>
        </div>
      </div>
    </button>
  );
}

function ConversationView({ thread }: { thread: MessageThread }) {
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center text-white font-semibold">
            {thread.clientName.charAt(0)}
          </div>
          <div>
            <p className="font-semibold text-gray-900">{thread.clientName}</p>
            <p className="text-xs text-gray-500">{thread.clientEmail}</p>
          </div>
        </div>
        <a
          href={`https://outlook.office.com/calendar/action/compose?subject=Meeting%20with%20${encodeURIComponent(thread.clientName)}&to=${encodeURIComponent(thread.clientEmail)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
        >
          Schedule Meeting
        </a>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {thread.messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.from === 'advisor' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[70%] px-4 py-3 text-sm ${
                msg.from === 'advisor'
                  ? 'bg-blue-600 text-white rounded-tl-lg rounded-tr-lg rounded-bl-lg'
                  : 'bg-gray-100 text-gray-900 rounded-tl-lg rounded-tr-lg rounded-br-lg'
              }`}
            >
              <p>{msg.text}</p>
              <p
                className={`text-xs mt-1 ${
                  msg.from === 'advisor' ? 'text-blue-200' : 'text-gray-400'
                }`}
              >
                {new Date(msg.timestamp).toLocaleString('en-AU', {
                  timeZone: 'Australia/Sydney',
                  hour: '2-digit',
                  minute: '2-digit',
                  day: 'numeric',
                  month: 'short',
                })}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Compose area (disabled for demo) */}
      <div className="px-6 py-4 border-t border-gray-100">
        <div className="relative">
          <textarea
            disabled
            placeholder="Type a message..."
            className="w-full px-4 py-3 border border-gray-200 rounded-lg text-sm resize-none bg-gray-50 cursor-not-allowed"
            rows={2}
          />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
            <span className="text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded font-medium">
              Demo Mode — responses are not sent
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function MessagesPage() {
  const [selectedThreadId, setSelectedThreadId] = useState(
    MESSAGE_THREADS[0]?.id,
  );
  const selectedThread = MESSAGE_THREADS.find((t) => t.id === selectedThreadId);

  return (
    <PageLayout title="Messages">
      <div
        className="bg-white rounded-xl border border-gray-200 flex overflow-hidden"
        style={{ height: 'calc(100vh - 200px)' }}
      >
        {/* Thread list */}
        <div className="w-1/3 border-r border-gray-200 overflow-y-auto">
          <div className="px-4 py-3 border-b border-gray-100">
            <h3 className="font-semibold text-sm text-gray-800">
              Conversations ({MESSAGE_THREADS.length})
            </h3>
          </div>
          <div className="divide-y divide-gray-50">
            {MESSAGE_THREADS.map((thread) => (
              <ThreadItem
                key={thread.id}
                thread={thread}
                isSelected={thread.id === selectedThreadId}
                onClick={() => setSelectedThreadId(thread.id)}
              />
            ))}
          </div>
        </div>

        {/* Conversation view */}
        <div className="flex-1">
          {selectedThread ? (
            <ConversationView thread={selectedThread} />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400">
              Select a conversation
            </div>
          )}
        </div>
      </div>
    </PageLayout>
  );
}
