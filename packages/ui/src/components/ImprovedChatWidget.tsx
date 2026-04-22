import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Plot from 'react-plotly.js';
import { useAuth } from 'react-oidc-context';
import { useRuntimeConfig } from '../hooks/useRuntimeConfig';
import {
  invokeRoutingAgent,
  listChatSessions,
  saveChatSessionLocally,
  saveMessagesForSession,
  loadMessagesForSession,
  ChatSession,
} from '../services/advisor-chat-service';
import { useVoiceAgent } from '../hooks/useVoiceAgent';

const MicIcon = ({ className }: { className?: string }) => (
  <svg
    className={className}
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M19 11a7 7 0 01-14 0m7 7v4m-4 0h8m-4-16a3 3 0 00-3 3v4a3 3 0 006 0V6a3 3 0 00-3-3z"
    />
  </svg>
);

const MicOffIcon = ({ className }: { className?: string }) => (
  <svg
    className={className}
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707A1 1 0 0112 5v14a1 1 0 01-1.707.707L5.586 15z"
    />
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2"
    />
  </svg>
);

interface QuoteData {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  prevClose: number;
  color: string;
}

interface MarketData {
  quotes: QuoteData[];
  chartData: {
    dates: string[];
    series: { symbol: string; values: number[]; color: string }[];
  };
  timeRange: string;
}

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: Date;
  stockData?: any;
  marketData?: MarketData;
  sources?: { title: string; url: string; date: string; source?: string }[];
}

function QuoteTable({ quotes }: { quotes: QuoteData[] }) {
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-gray-700 text-xs">
            <th className="text-left py-3 px-4 font-bold">Symbol</th>
            <th className="text-right py-3 px-4 font-bold">Price</th>
            <th className="text-right py-3 px-4 font-bold">Change</th>
            <th className="text-right py-3 px-4 font-bold">% Change</th>
            <th className="text-right py-3 px-4 font-bold">Prev Close</th>
          </tr>
        </thead>
        <tbody>
          {quotes.map((q, i) => {
            const isUp = q.change >= 0;
            const color = isUp ? 'text-green-600' : 'text-red-500';
            const arrow = isUp ? '↑' : '↓';
            return (
              <tr
                key={q.symbol}
                className={
                  (i < quotes.length - 1 ? 'border-b border-gray-50' : '') +
                  ' hover:bg-gray-50 transition-colors'
                }
              >
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-3 h-3 rounded-sm inline-block"
                      style={{ backgroundColor: q.color }}
                    />
                    <div>
                      <div className="font-medium text-gray-900">
                        {q.symbol}
                      </div>
                      <div className="text-xs text-gray-500">{q.name}</div>
                    </div>
                  </div>
                </td>
                <td className="text-right py-3 px-4 font-medium text-gray-900">
                  {q.price.toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </td>
                <td className={`text-right py-3 px-4 font-medium ${color}`}>
                  {isUp ? '+' : ''}
                  {q.change.toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}{' '}
                  {arrow}
                </td>
                <td className={`text-right py-3 px-4 font-medium ${color}`}>
                  {isUp ? '+' : ''}
                  {q.changePercent.toFixed(2)}% {arrow}
                </td>
                <td className="text-right py-3 px-4 text-gray-600">
                  {q.prevClose.toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// Google Finance-style x-axis formatting per time range
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function xaxisForRange(range: string): any {
  const base = {
    gridcolor: '#f3f4f6',
    tickfont: { size: 10, color: '#9ca3af' },
    type: 'date' as const,
  };
  switch (range) {
    case '1D':
      // 9:30 AM, 11:30 AM... (every 2 hours)
      return { ...base, tickformat: '%I:%M %p', dtick: 3600000 * 2 };
    case '5D':
      // Mon, Tue, Wed... (one tick per trading day)
      return { ...base, tickformat: '%a', dtick: 86400000 };
    case '1M':
      // Mar 3, Mar 10... (weekly)
      return { ...base, tickformat: '%b %e', dtick: 86400000 * 7 };
    case '6M':
      // Oct, Nov, Dec... (monthly)
      return { ...base, tickformat: '%b', dtick: 'M1' };
    case 'YTD':
      // Jan, Feb, Mar... (monthly)
      return { ...base, tickformat: '%b', dtick: 'M1' };
    case '1Y':
      // Jun '25, Sep '25... (quarterly)
      return { ...base, tickformat: "%b '%y", dtick: 'M3' };
    case '5Y':
      // 2022, 2023, 2024... (yearly)
      return { ...base, tickformat: '%Y', dtick: 'M12' };
    case 'MAX':
      // 1990, 1995, 2000... (every 5 years)
      return { ...base, tickformat: '%Y', dtick: 'M60' };
    default:
      return { ...base, tickformat: '%b %e', dtick: 86400000 * 7 };
  }
}

function ComparisonChart({
  chartData,
  quotes,
  timeRanges,
  selectedRange,
  onRangeChange,
  agentOpts,
  apiUrl,
}: {
  chartData: MarketData['chartData'];
  quotes: QuoteData[];
  timeRanges: string[];
  selectedRange: string;
  onRangeChange: (r: string, newData: MarketData) => void;
  agentOpts: Parameters<typeof invokeRoutingAgent>[1] | null;
  apiUrl: string;
}) {
  const [loading, setLoading] = useState(false);
  const [currentData, setCurrentData] = useState(chartData);
  const [activeRange, setActiveRange] = useState(selectedRange);

  const handleRangeClick = async (range: string) => {
    setActiveRange(range);
    setLoading(true);
    try {
      const tickers = currentData.series.map((s) => s.symbol).join(',');
      if (agentOpts) {
        // Production: call AgentCore
        const result = await invokeRoutingAgent(
          `__chart__ ${tickers} ${range}`,
          agentOpts,
        );
        if (result.marketData?.chartData?.dates?.length) {
          setCurrentData(result.marketData.chartData);
          onRangeChange(range, result.marketData);
        }
      } else {
        // Local dev: call /chart endpoint directly
        const resp = await fetch(
          `${apiUrl}/chart?tickers=${encodeURIComponent(tickers)}&range=${range}`,
        );
        if (resp.ok) {
          const data = await resp.json();
          if (data?.chartData?.dates?.length) {
            setCurrentData(data.chartData);
            onRangeChange(range, data);
          }
        }
      }
    } catch (e) {
      console.error('Chart fetch error:', e);
    } finally {
      setLoading(false);
    }
  };

  // For single stock, determine color based on price vs prevClose
  const isSingle = currentData.series.length === 1;
  const prevClose = isSingle && quotes.length > 0 ? quotes[0].prevClose : 0;
  const lastPrice =
    isSingle && currentData.series[0]?.values?.length
      ? currentData.series[0].values[currentData.series[0].values.length - 1]
      : 0;
  const isUp = !isSingle || lastPrice >= prevClose;
  const lineColor = isSingle ? (isUp ? '#34a853' : '#ea4335') : undefined;

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white">
      <div className="flex gap-2 mb-2">
        {currentData.series.map((s) => (
          <span
            key={s.symbol}
            className="flex items-center gap-1 text-xs text-gray-600 border border-gray-200 rounded-full px-2 py-1"
          >
            <span
              className="w-2.5 h-2.5 rounded-sm"
              style={{ backgroundColor: lineColor || s.color }}
            />
            {s.symbol}
          </span>
        ))}
      </div>
      <div className="h-64 relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/70 z-10">
            <span className="text-sm text-gray-400">Loading...</span>
          </div>
        )}
        <Plot
          data={[
            ...currentData.series.map((s) => {
              // For multi-stock, normalize to % change so different price scales are comparable
              const values =
                !isSingle && s.values.length > 0
                  ? s.values.map(
                      (v) =>
                        Math.round(((v / s.values[0]) * 100 - 100) * 100) / 100,
                    )
                  : s.values;
              return {
                x: currentData.dates,
                y: values,
                type: 'scatter' as const,
                mode: 'lines' as const,
                line: { color: lineColor || s.color, width: 2 },
                name: s.symbol,
                hovertemplate: isSingle
                  ? `${s.symbol}: $%{y:,.2f}<extra></extra>`
                  : `${s.symbol}: %{y:.2f}%<extra></extra>`,
              };
            }),
          ]}
          layout={{
            autosize: true,
            margin: { l: 60, r: 10, t: 10, b: 30 },
            xaxis: xaxisForRange(activeRange),
            yaxis: {
              autorange: true,
              gridcolor: '#f3f4f6',
              tickfont: { size: 10, color: '#9ca3af' },
              tickprefix: isSingle ? '$' : '',
              ticksuffix: isSingle ? '' : '%',
            },
            plot_bgcolor: '#ffffff',
            paper_bgcolor: '#ffffff',
            showlegend: false,
            hovermode: 'x unified' as const,
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: '100%', height: '100%' }}
        />
      </div>
      <div className="flex gap-1 mt-3">
        {timeRanges.map((r) => (
          <button
            key={r}
            onClick={() => handleRangeClick(r)}
            className={`px-3 py-1 text-xs rounded-full ${
              activeRange === r
                ? 'bg-gray-900 text-white'
                : 'text-gray-500 hover:bg-gray-100'
            }`}
          >
            {r}
          </button>
        ))}
      </div>
    </div>
  );
}

export function ImprovedChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [statusText, setStatusText] = useState('');
  const [activeAgent, setActiveAgent] = useState('');
  const [selectedTimeRange, setSelectedTimeRange] = useState('1M');
  const [showHistory, setShowHistory] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const runtimeConfig = useRuntimeConfig();
  const auth = useAuth();
  const accessToken = auth?.user?.access_token;
  const idToken = auth?.user?.id_token;

  const voice = useVoiceAgent({
    voiceGatewayArn: runtimeConfig.voiceGatewayArn,
    region: runtimeConfig.cognitoProps?.region,
    accessToken: idToken,
    identityPoolId: runtimeConfig.cognitoProps?.identityPoolId,
    userPoolId: runtimeConfig.cognitoProps?.userPoolId,
  });

  const toggleVoice = useCallback(async () => {
    if (voice.isRecording) {
      voice.stopRecording();
      if (!voice.isMuted) voice.toggleMute();
    } else {
      if (!voice.isConnected) await voice.connect();
      if (voice.isMuted) voice.toggleMute();
      await voice.startRecording();
      setIsExpanded(true);
    }
  }, [voice]);

  // Prod: runtime-config.json IntelligenceApi URL
  // Local dev: fallback to localhost:9000 (advisor_chat A2A)
  const apiUrl = (
    runtimeConfig.intelligenceApiUrl || 'http://localhost:9000'
  ).replace(/\/+$/, '');

  const timeRanges = ['1D', '5D', '1M', '6M', 'YTD', '1Y', '5Y', 'MAX'];

  // Close session when chat window closes — save and clear
  const closeChat = useCallback(() => {
    const sessionId = localStorage.getItem('chat_session_id');
    if (sessionId && messages.length > 0) {
      saveMessagesForSession(sessionId, messages);
      const firstUserMsg = messages.find((m) => m.sender === 'user');
      if (firstUserMsg) {
        saveChatSessionLocally(sessionId, firstUserMsg.text);
      }
    }
    setIsOpen(false);
    setIsExpanded(false);
    setMessages([]);
    setShowHistory(false);
  }, [messages]);

  // Load conversation history
  const loadHistory = useCallback(async () => {
    setShowHistory((prev) => !prev);
    const { routingAgentArn, cognitoProps } = runtimeConfig;
    const prodOpts =
      routingAgentArn && cognitoProps && accessToken
        ? { routingAgentArn, region: cognitoProps.region, accessToken }
        : undefined;
    const list = await listChatSessions(apiUrl, prodOpts);
    setSessions(list);
  }, [apiUrl, runtimeConfig, accessToken]);

  // Start a new conversation — save current first, then reset
  const startNewChat = useCallback(() => {
    const oldId = localStorage.getItem('chat_session_id');
    if (oldId && messages.length > 0) {
      saveMessagesForSession(oldId, messages);
      const firstUserMsg = messages.find((m) => m.sender === 'user');
      if (firstUserMsg) {
        saveChatSessionLocally(oldId, firstUserMsg.text);
      }
    }
    const newId = `session_${Date.now()}`;
    localStorage.setItem('chat_session_id', newId);
    setMessages([]);
    setShowHistory(false);
  }, [messages]);

  // Resume a past conversation — save current, then load selected
  const resumeSession = useCallback(
    (session: ChatSession) => {
      const currentId = localStorage.getItem('chat_session_id');
      // Skip if already on this session
      if (currentId === session.session_id) {
        setShowHistory(false);
        return;
      }
      if (currentId && messages.length > 0) {
        saveMessagesForSession(currentId, messages);
        const firstUserMsg = messages.find((m) => m.sender === 'user');
        if (firstUserMsg) {
          saveChatSessionLocally(currentId, firstUserMsg.text);
        }
      }
      localStorage.setItem('chat_session_id', session.session_id);
      setMessages(loadMessagesForSession(session.session_id));
      setShowHistory(false);
    },
    [messages],
  );

  const agentOpts = (() => {
    const { routingAgentArn, cognitoProps } = runtimeConfig;
    const sessionId =
      localStorage.getItem('chat_session_id') || `session_${Date.now()}`;
    if (routingAgentArn && cognitoProps && accessToken) {
      return {
        routingAgentArn,
        region: cognitoProps.region,
        accessToken,
        sessionId,
      };
    }
    return null;
  })();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, statusText, activeAgent]);

  // Persist messages to localStorage whenever they change
  useEffect(() => {
    const sid = localStorage.getItem('chat_session_id');
    if (sid && messages.length > 0) {
      saveMessagesForSession(sid, messages);
    }
  }, [messages]);

  const handleSend = useCallback(
    async (messageText?: string, timeRange?: string) => {
      const textToSend = messageText || inputValue;
      if (!textToSend.trim()) return;

      // Build conversation context from recent messages (last 10)
      const recent = messages.slice(-10);
      let contextPrefix = '';
      if (recent.length > 0) {
        const history = recent
          .map(
            (m) =>
              `${m.sender === 'user' ? 'User' : 'Assistant'}: ${m.text.slice(0, 300)}`,
          )
          .join('\n');
        contextPrefix = `[Conversation so far]\n${history}\n[Current message]\n`;
      }
      const messageWithContext = contextPrefix + textToSend;

      const userMessage: Message = {
        id: Date.now().toString(),
        text: textToSend,
        sender: 'user',
        timestamp: new Date(),
      };

      if (!messageText) {
        setMessages((prev) => [...prev, userMessage]);
      }
      setInputValue('');
      setIsLoading(true);
      setStatusText('Connecting...');
      setIsExpanded(true);

      const sessionId =
        localStorage.getItem('chat_session_id') || `session_${Date.now()}`;
      localStorage.setItem('chat_session_id', sessionId);

      // Register session in history on first message of this session
      saveChatSessionLocally(sessionId, textToSend);

      try {
        const { routingAgentArn, cognitoProps } = runtimeConfig;

        let cleanText = 'I received your message.';
        let agentMarketData: MarketData | null = null;
        let agentSources:
          | { title: string; url: string; date: string }[]
          | null = null;

        // Build SSE request — same streaming for prod and local dev
        let streamUrl: string;
        const headers: Record<string, string> = {
          Accept: 'text/event-stream',
        };

        if (routingAgentArn && cognitoProps && accessToken) {
          // Production: SSE via AgentCore /invocations with Bearer auth
          const arnEncoded = encodeURIComponent(routingAgentArn);
          streamUrl = `https://bedrock-agentcore.${cognitoProps.region}.amazonaws.com/runtimes/${arnEncoded}/invocations`;
          headers['Content-Type'] = 'application/json';
          headers['Authorization'] = `Bearer ${accessToken}`;
          headers['x-amz-bedrock-agentcore-runtime-session-id'] = sessionId;
        } else {
          // Local dev: SSE via /chat/stream GET
          const params = new URLSearchParams({
            message: messageWithContext,
            session_id: sessionId,
          });
          if (timeRange || selectedTimeRange) {
            params.set('time_range', timeRange || selectedTimeRange);
          }
          streamUrl = `${apiUrl}/chat/stream?${params}`;
        }

        // Build fetch options
        const fetchOpts: RequestInit = {
          headers,
          signal: AbortSignal.timeout(120000),
        };
        if (routingAgentArn && cognitoProps && accessToken) {
          fetchOpts.method = 'POST';
          fetchOpts.body = JSON.stringify({
            jsonrpc: '2.0',
            id: 1,
            method: 'message/send',
            params: {
              message: {
                kind: 'message',
                role: 'user',
                messageId: sessionId,
                parts: [{ kind: 'text', text: messageWithContext }],
              },
            },
          });
        }

        const response = await fetch(streamUrl, fetchOpts);

        if (!response.ok || !response.body) {
          throw new Error(`Stream unavailable (${response.status})`);
        }

        cleanText = '';
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let handled = false;

        // Add a placeholder bot message for streaming
        const streamMsgId = (Date.now() + 1).toString();
        setMessages((prev) => [
          ...prev,
          {
            id: streamMsgId,
            text: '',
            sender: 'bot',
            timestamp: new Date(),
          },
        ]);

        const updateStreamMsg = (text: string) =>
          setMessages((prev) =>
            prev.map((m) => (m.id === streamMsgId ? { ...m, text } : m)),
          );

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          let eventType = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ') && eventType) {
              try {
                const data = JSON.parse(line.slice(6));
                if (eventType === 'status') {
                  setStatusText(data.message);
                } else if (eventType === 'agent_start') {
                  setActiveAgent(data.agent);
                  setStatusText('');
                } else if (eventType === 'agent_end') {
                  setActiveAgent('');
                } else if (eventType === 'token') {
                  cleanText += data.text;
                  updateStreamMsg(cleanText);
                } else if (eventType === 'done') {
                  cleanText = (data.message || cleanText).replace(
                    /<thinking>[\s\S]*?<\/thinking>\s*/g,
                    '',
                  );
                  if (data.marketData) {
                    agentMarketData = data.marketData;
                  }
                  if (data.sources) {
                    agentSources = data.sources;
                  }
                  handled = true;
                } else if (eventType === 'error') {
                  cleanText = `Error: ${data.message}`;
                  handled = true;
                }
              } catch {
                // ignore malformed JSON
              }
              eventType = '';
            }
          }
        }
        if (!handled) throw new Error('No response from stream');

        // Update the streaming message with final response + market data
        setMessages((prev) =>
          prev.map((m) =>
            m.id === streamMsgId
              ? {
                  ...m,
                  text: cleanText,
                  ...(agentMarketData ? { marketData: agentMarketData } : {}),
                  ...(agentSources ? { sources: agentSources } : {}),
                }
              : m,
          ),
        );
      } catch (error) {
        console.error('Chat error:', error);
        setMessages((prev) => [
          ...prev,
          {
            id: (Date.now() + 1).toString(),
            text: `Sorry, I encountered an error. Please try again.`,
            sender: 'bot',
            timestamp: new Date(),
          },
        ]);
      } finally {
        setIsLoading(false);
        setStatusText('');
        setActiveAgent('');
      }
    },
    [
      inputValue,
      messages,
      selectedTimeRange,
      apiUrl,
      runtimeConfig,
      accessToken,
    ],
  );

  return (
    <>
      {!isOpen && (
        <button
          onClick={() => {
            setIsOpen(true);
            // Start fresh — new session each time chat opens
            const newId = `session_${Date.now()}`;
            localStorage.setItem('chat_session_id', newId);
            setMessages([]);
          }}
          className="fixed bottom-6 right-6 w-14 h-14 bg-indigo-600 text-white rounded-full shadow-lg hover:bg-indigo-700 transition-all flex items-center justify-center z-50"
        >
          💬
        </button>
      )}

      {/* Compact Input Bar */}
      {isOpen && !isExpanded && (
        <div className="fixed bottom-0 left-64 right-0 bg-white border-t shadow-lg p-4 z-40">
          <div className="max-w-full mx-auto flex items-center gap-3 bg-white rounded-full px-4 py-2 border border-gray-300 shadow-sm">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask about stocks, portfolios, or market insights"
              className="flex-1 bg-transparent focus:outline-none text-gray-900 placeholder-gray-400 text-sm ml-2"
            />
            <button
              onClick={() => handleSend()}
              disabled={!inputValue.trim() || isLoading}
              className="w-9 h-9 bg-indigo-600 text-white rounded-full hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center flex-shrink-0 transition-colors"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 10l7-7m0 0l7 7m-7-7v18"
                />
              </svg>
            </button>
            <button
              onClick={toggleVoice}
              className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${voice.isRecording ? 'bg-red-500 text-white animate-pulse' : 'text-gray-400 hover:text-indigo-600 hover:bg-gray-100'}`}
              title={voice.isRecording ? 'Stop voice' : 'Start voice'}
            >
              {voice.isRecording ? (
                <MicOffIcon className="w-4 h-4" />
              ) : (
                <MicIcon className="w-4 h-4" />
              )}
            </button>
            <button
              onClick={closeChat}
              className="w-9 h-9 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100 flex items-center justify-center flex-shrink-0 transition-colors"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Expanded Chat Panel */}
      {isExpanded && (
        <div className="fixed top-0 left-64 right-0 bottom-0 bg-gray-50 shadow-2xl z-30 overflow-hidden animate-slideUp">
          <div className="flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200">
              <div className="flex items-center gap-3">
                <button
                  onClick={loadHistory}
                  className="w-8 h-8 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100 flex items-center justify-center transition-colors"
                  title="Conversation history"
                >
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 6h16M4 12h16M4 18h16"
                    />
                  </svg>
                </button>
                <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center">
                  <span className="text-sm text-white">💬</span>
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-gray-900">
                    Advisor Chat
                  </h2>
                  <p className="text-xs text-gray-400">
                    Wealth management assistant
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={startNewChat}
                  className="w-8 h-8 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 flex items-center justify-center transition-colors"
                  title="New conversation"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 4v16m8-8H4"
                    />
                  </svg>
                </button>
                <button
                  onClick={() => setIsExpanded(false)}
                  className="w-8 h-8 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 flex items-center justify-center transition-colors"
                  title="Minimize"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </button>
                <button
                  onClick={closeChat}
                  className="w-8 h-8 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 flex items-center justify-center transition-colors"
                  title="Close"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>
            </div>

            {/* Conversation History Sidebar */}
            {showHistory && (
              <div className="absolute top-12 left-0 bottom-0 w-72 bg-white border-r border-gray-200 z-40 overflow-y-auto shadow-lg">
                <div className="p-4 border-b border-gray-100">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-gray-700">
                      History
                    </h3>
                    <button
                      onClick={() => setShowHistory(false)}
                      className="w-6 h-6 text-gray-400 hover:text-gray-600 rounded flex items-center justify-center"
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </div>
                </div>
                <button
                  onClick={startNewChat}
                  className="w-full px-4 py-3 text-left text-sm text-indigo-600 hover:bg-indigo-50 border-b border-gray-100 flex items-center gap-2"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 4v16m8-8H4"
                    />
                  </svg>
                  New conversation
                </button>
                {sessions.length === 0 && (
                  <p className="px-4 py-6 text-xs text-gray-400 text-center">
                    No past conversations
                  </p>
                )}
                {sessions.map((s) => (
                  <button
                    key={s.session_id}
                    onClick={() => resumeSession(s)}
                    className={`w-full px-4 py-3 text-left hover:bg-gray-50 border-b border-gray-50 transition-colors ${
                      localStorage.getItem('chat_session_id') === s.session_id
                        ? 'bg-indigo-50'
                        : ''
                    }`}
                  >
                    <p className="text-sm text-gray-800 truncate">{s.title}</p>
                    {s.created_at && (
                      <p className="text-[10px] text-gray-400 mt-0.5">
                        {new Date(s.created_at).toLocaleDateString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </p>
                    )}
                  </button>
                ))}
              </div>
            )}

            <div className="flex-1 overflow-y-auto p-6 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent hover:scrollbar-thumb-gray-400">
              {messages.length === 0 && !isLoading && (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <div className="w-12 h-12 rounded-full bg-indigo-600 flex items-center justify-center mb-4">
                    <span className="text-xl text-white">💬</span>
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-1">
                    Wealth Advisor
                  </h3>
                  <p className="text-sm text-gray-500 mb-6">
                    Ask about stocks, portfolios, or market insights
                  </p>
                </div>
              )}
              {messages.map((message) => (
                <div key={message.id} className="mb-6 animate-fadeIn">
                  {message.sender === 'user' ? (
                    <div className="flex justify-end mb-1">
                      <div>
                        <div className="bg-indigo-600 text-white rounded-2xl rounded-br-sm px-5 py-3 max-w-2xl">
                          <p className="text-sm">{message.text}</p>
                        </div>
                        <p className="text-[10px] text-gray-400 text-right mt-1 mr-1">
                          {message.timestamp.toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex gap-3">
                      <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0 mt-1">
                        <span className="text-xs text-white">💬</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="space-y-4">
                          <div className="text-gray-800 leading-relaxed prose prose-sm max-w-none">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                h1: ({ children }) => (
                                  <h1 className="text-base font-bold text-gray-900 mt-4 mb-2">
                                    {children}
                                  </h1>
                                ),
                                h2: ({ children }) => (
                                  <h2 className="text-sm font-bold text-gray-800 mt-4 mb-2">
                                    {children}
                                  </h2>
                                ),
                                h3: ({ children }) => (
                                  <h3 className="text-sm font-semibold text-gray-800 mt-4 mb-2 flex items-center gap-1">
                                    {children}
                                  </h3>
                                ),
                                p: ({ children }) => (
                                  <p className="text-sm text-gray-700 my-1.5 leading-relaxed">
                                    {children}
                                  </p>
                                ),
                                blockquote: ({ children }) => (
                                  <blockquote className="border-l-3 border-indigo-300 pl-3 my-2 text-sm text-gray-600 italic">
                                    {children}
                                  </blockquote>
                                ),
                                hr: () => (
                                  <hr className="my-3 border-gray-200" />
                                ),
                                a: ({ href, children }) => (
                                  <a
                                    href={href}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-indigo-600 hover:text-indigo-800 underline"
                                  >
                                    {children}
                                  </a>
                                ),
                                ul: ({ children }) => (
                                  <ul className="space-y-1.5 my-2">
                                    {children}
                                  </ul>
                                ),
                                ol: ({ children }) => (
                                  <ol className="space-y-1.5 my-2 list-decimal list-inside">
                                    {children}
                                  </ol>
                                ),
                                li: ({ children }) => (
                                  <li className="text-sm text-gray-600 flex items-start gap-2">
                                    <span className="text-gray-300 mt-1.5 text-[6px]">
                                      ●
                                    </span>
                                    <span>{children}</span>
                                  </li>
                                ),
                                table: ({ children }) => (
                                  <div className="overflow-x-auto my-3 rounded-lg border border-gray-200">
                                    <table className="w-full text-sm">
                                      {children}
                                    </table>
                                  </div>
                                ),
                                thead: ({ children }) => (
                                  <thead className="bg-gray-50 border-b border-gray-200">
                                    {children}
                                  </thead>
                                ),
                                th: ({ children }) => (
                                  <th className="px-3 py-2 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                                    {children}
                                  </th>
                                ),
                                td: ({ children }) => (
                                  <td className="px-3 py-2 text-gray-700 border-b border-gray-100">
                                    {children}
                                  </td>
                                ),
                              }}
                            >
                              {message.text
                                .replace(
                                  /<thinking>[\s\S]*?<\/thinking>\s*/g,
                                  '',
                                )
                                .replace(
                                  /```(?:markdown)?\s*\n?([\s\S]*?)```/g,
                                  '$1',
                                )
                                .trim()}
                            </ReactMarkdown>
                          </div>

                          {message.marketData && (
                            <div className="space-y-4">
                              <ComparisonChart
                                chartData={message.marketData.chartData}
                                quotes={message.marketData.quotes}
                                timeRanges={timeRanges}
                                selectedRange={
                                  message.marketData.timeRange ||
                                  selectedTimeRange
                                }
                                onRangeChange={(range, newData) => {
                                  setSelectedTimeRange(range);
                                }}
                                agentOpts={agentOpts}
                                apiUrl={apiUrl}
                              />
                              <QuoteTable quotes={message.marketData.quotes} />
                            </div>
                          )}

                          {message.stockData && !message.marketData && (
                            <div className="space-y-4">
                              <div className="border border-gray-200 rounded-lg p-4 bg-white">
                                <div className="h-64">
                                  <Plot
                                    data={[
                                      {
                                        x:
                                          message.stockData.chartData?.map(
                                            (d: any) => d.time,
                                          ) || [],
                                        y:
                                          message.stockData.chartData?.map(
                                            (d: any) => d.price,
                                          ) || [],
                                        type: 'scatter' as const,
                                        mode: 'lines' as const,
                                        line: { color: '#4285f4', width: 2 },
                                        name: message.stockData.symbol,
                                      },
                                    ]}
                                    layout={{
                                      autosize: true,
                                      margin: { l: 40, r: 10, t: 10, b: 30 },
                                      xaxis: {
                                        gridcolor: '#f3f4f6',
                                        tickfont: {
                                          size: 10,
                                          color: '#9ca3af',
                                        },
                                      },
                                      yaxis: {
                                        gridcolor: '#f3f4f6',
                                        tickfont: {
                                          size: 10,
                                          color: '#9ca3af',
                                        },
                                        tickprefix: '$',
                                      },
                                      plot_bgcolor: '#ffffff',
                                      paper_bgcolor: '#ffffff',
                                      showlegend: false,
                                    }}
                                    config={{
                                      displayModeBar: false,
                                      responsive: true,
                                    }}
                                    style={{ width: '100%', height: '100%' }}
                                  />
                                </div>
                                <div className="flex gap-1 mt-3">
                                  {timeRanges.map((range) => (
                                    <button
                                      key={range}
                                      onClick={() => {
                                        setSelectedTimeRange(range);
                                        const lastUserMsg = messages
                                          .filter((m) => m.sender === 'user')
                                          .pop();
                                        if (lastUserMsg)
                                          handleSend(lastUserMsg.text, range);
                                      }}
                                      className={`px-3 py-1 text-xs rounded-full ${
                                        selectedTimeRange === range
                                          ? 'bg-gray-900 text-white'
                                          : 'text-gray-500 hover:bg-gray-100'
                                      }`}
                                    >
                                      {range}
                                    </button>
                                  ))}
                                </div>
                              </div>
                              <QuoteTable
                                quotes={[
                                  {
                                    symbol: message.stockData.symbol,
                                    name: message.stockData.symbol,
                                    price: message.stockData.price || 0,
                                    change: message.stockData.change || 0,
                                    changePercent:
                                      message.stockData.changePercent || 0,
                                    prevClose: message.stockData.price
                                      ? message.stockData.price -
                                        (message.stockData.change || 0)
                                      : 0,
                                    color: '#4285f4',
                                  },
                                ]}
                              />
                            </div>
                          )}

                          {message.sources && message.sources.length > 0 && (
                            <div className="mt-3 pt-3 border-t border-gray-100">
                              <p className="text-xs font-semibold text-gray-500 mb-1.5">
                                📰 Sources
                              </p>
                              <div className="flex flex-wrap gap-1.5">
                                {(() => {
                                  const getDomain = (s: {
                                    source?: string;
                                    url: string;
                                  }) =>
                                    s.source ||
                                    new URL(s.url).hostname.replace(
                                      /^www\./,
                                      '',
                                    );
                                  const seen = new Set<string>();
                                  return message.sources
                                    .filter((s) => {
                                      const d = getDomain(s);
                                      if (seen.has(d)) return false;
                                      seen.add(d);
                                      return true;
                                    })
                                    .map((s, i) => (
                                      <a
                                        key={i}
                                        href={s.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-gray-50 border border-gray-200 rounded-full text-indigo-600 hover:bg-indigo-50 hover:border-indigo-200 transition-colors"
                                        title={s.title}
                                      >
                                        {getDomain(s)}
                                      </a>
                                    ));
                                })()}
                              </div>
                            </div>
                          )}
                        </div>
                        <p className="text-[10px] text-gray-400 mt-1 ml-1">
                          {message.timestamp.toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {/* Voice conversation turns */}
              {voice.conversationHistory.map((turn, i) => (
                <div
                  key={`voice-${i}`}
                  className={`flex gap-3 mb-4 ${turn.role === 'user' ? 'justify-end' : ''}`}
                >
                  {turn.role === 'assistant' && (
                    <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0">
                      <span className="text-xs text-white">🎙</span>
                    </div>
                  )}
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${turn.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-white border border-gray-100 text-gray-800'}`}
                  >
                    {turn.transcript}
                  </div>
                </div>
              ))}

              {/* Live voice transcripts */}
              {voice.userTranscript && (
                <div className="flex gap-3 mb-4 justify-end">
                  <div className="max-w-[80%] rounded-2xl px-4 py-2 text-sm bg-indigo-400 text-white opacity-70 italic">
                    {voice.userTranscript}…
                  </div>
                </div>
              )}
              {voice.isThinking && (
                <div className="flex gap-3 mb-4">
                  <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0">
                    <span className="text-xs text-white">🎙</span>
                  </div>
                  <div className="max-w-[80%] rounded-2xl px-4 py-2 text-sm bg-white border border-gray-100 text-gray-400">
                    {voice.thinkingStatus && (
                      <span className="block text-xs text-indigo-500 mb-1">
                        {voice.thinkingStatus}
                      </span>
                    )}
                    <span className="inline-flex gap-1">
                      <span className="animate-bounce">●</span>
                      <span className="animate-bounce [animation-delay:0.15s]">
                        ●
                      </span>
                      <span className="animate-bounce [animation-delay:0.3s]">
                        ●
                      </span>
                    </span>
                  </div>
                </div>
              )}
              {voice.agentTranscript && (
                <div className="flex gap-3 mb-4">
                  <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0">
                    <span className="text-xs text-white">🎙</span>
                  </div>
                  <div className="max-w-[80%] rounded-2xl px-4 py-2 text-sm bg-white border border-gray-100 text-gray-800">
                    {voice.agentTranscript}
                  </div>
                </div>
              )}

              {voice.error && (
                <div className="text-xs text-red-500 text-center mb-2">
                  {voice.error}
                </div>
              )}

              {isLoading && (
                <div className="flex gap-3 mb-6">
                  <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0">
                    <span className="text-xs text-white">💬</span>
                  </div>
                  <div className="bg-white rounded-2xl px-4 py-3 border border-gray-100">
                    <div className="flex items-center gap-2">
                      <span className="flex gap-1">
                        <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" />
                        <span
                          className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce"
                          style={{ animationDelay: '0.15s' }}
                        />
                        <span
                          className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce"
                          style={{ animationDelay: '0.3s' }}
                        />
                      </span>
                      {activeAgent && (
                        <span className="text-xs font-medium text-indigo-600 ml-1">
                          {activeAgent}
                        </span>
                      )}
                      {statusText && (
                        <span className="text-xs text-gray-500 ml-1">
                          {statusText}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input in expanded view */}
            <div className="px-6 py-4 bg-white border-t border-gray-200">
              <div className="flex items-center gap-3 bg-gray-50 rounded-full px-4 py-2 border border-gray-200">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                  placeholder="Ask about stocks, portfolios, or market insights"
                  className="flex-1 bg-transparent focus:outline-none text-gray-900 placeholder-gray-400 text-sm ml-2"
                />
                <button
                  onClick={() => handleSend()}
                  disabled={!inputValue.trim() || isLoading}
                  className="w-9 h-9 bg-indigo-600 text-white rounded-full hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center flex-shrink-0 transition-colors"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 10l7-7m0 0l7 7m-7-7v18"
                    />
                  </svg>
                </button>
                <button
                  onClick={toggleVoice}
                  className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${voice.isRecording ? 'bg-red-500 text-white animate-pulse' : 'text-gray-400 hover:text-indigo-600 hover:bg-gray-100'}`}
                  title={voice.isRecording ? 'Stop voice' : 'Start voice'}
                >
                  {voice.isRecording ? (
                    <MicOffIcon className="w-4 h-4" />
                  ) : (
                    <MicIcon className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
