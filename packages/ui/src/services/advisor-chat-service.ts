/**
 * Invoke the routing agent via AgentCore directly from the browser.
 * Bypasses API Gateway 29s timeout. Uses Cognito JWT for auth —
 * the AgentCore Runtime validates the token automatically.
 */
export async function invokeRoutingAgent(
  message: string,
  opts: {
    routingAgentArn: string;
    region: string;
    accessToken: string;
    sessionId: string;
    refreshToken?: () => Promise<string>;
  },
): Promise<{ text: string; marketData: any; sources: any }> {
  const { routingAgentArn, region, accessToken, sessionId } = opts;

  const arnEncoded = encodeURIComponent(routingAgentArn);
  const url = `https://bedrock-agentcore.${region}.amazonaws.com/runtimes/${arnEncoded}/invocations`;

  const payload = JSON.stringify({
    jsonrpc: '2.0',
    id: 1,
    method: 'message/send',
    params: {
      message: {
        kind: 'message',
        role: 'user',
        messageId: sessionId,
        parts: [{ kind: 'text', text: message }],
      },
    },
  });

  const doFetch = async (token: string) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        Authorization: `Bearer ${token}`,
        'x-amz-bedrock-agentcore-runtime-session-id': sessionId,
      },
      body: payload,
      signal: controller.signal,
    });
    clearTimeout(timeout);
    return response;
  };

  let response = await doFetch(accessToken);

  // Retry once with refreshed token on 401 (expired JWT)
  if (response.status === 401 && opts.refreshToken) {
    const freshToken = await opts.refreshToken();
    response = await doFetch(freshToken);
  }

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`AgentCore ${response.status}: ${errText}`);
  }

  const body = await response.json();
  const result = body?.result ?? body;
  let text = '';
  let marketData = null;
  let sources = null;
  for (const artifact of result?.artifacts ?? []) {
    for (const part of artifact?.parts ?? []) {
      if (part?.kind === 'text' && part?.text) {
        const mdMatch = part.text.match(/^<!--MARKET_DATA:([\s\S]+)-->$/);
        const srcMatch = part.text.match(/^<!--SOURCES:([\s\S]+)-->$/);
        if (mdMatch) {
          try {
            marketData = JSON.parse(mdMatch[1]);
          } catch {
            /* ignore */
          }
        } else if (srcMatch) {
          try {
            sources = JSON.parse(srcMatch[1]);
          } catch {
            /* ignore */
          }
        } else if (!text) {
          text = part.text;
        }
      }
    }
  }
  return {
    text: text || JSON.stringify(body),
    marketData: marketData ?? result?.marketData ?? null,
    sources,
  };
}

export interface ChatSession {
  session_id: string;
  title: string;
  created_at: string;
}

export async function listChatSessions(
  apiUrl: string,
  opts?: {
    routingAgentArn: string;
    region: string;
    accessToken: string;
  },
): Promise<ChatSession[]> {
  try {
    if (opts?.routingAgentArn) {
      // Production: sessions stored in localStorage, filtered to 30 days
      const raw = localStorage.getItem('chat_sessions') || '[]';
      const all: ChatSession[] = JSON.parse(raw);
      const thirtyDaysAgo = Date.now() - 30 * 24 * 60 * 60 * 1000;
      const valid = all.filter(
        (s) =>
          !s.created_at || new Date(s.created_at).getTime() > thirtyDaysAgo,
      );
      if (valid.length < all.length) {
        localStorage.setItem('chat_sessions', JSON.stringify(valid));
        // Clean up message data for expired sessions
        const validIds = new Set(valid.map((s) => s.session_id));
        all
          .filter((s) => !validIds.has(s.session_id))
          .forEach((s) => localStorage.removeItem(`chat_msgs_${s.session_id}`));
      }
      return valid;
    }
    const resp = await fetch(`${apiUrl}/chat/sessions`);
    if (!resp.ok) return [];
    const data = await resp.json();
    return data.sessions || [];
  } catch {
    return [];
  }
}

export function saveChatSessionLocally(
  sessionId: string,
  firstMessage: string,
): void {
  try {
    const raw = localStorage.getItem('chat_sessions') || '[]';
    const sessions: ChatSession[] = JSON.parse(raw);
    if (sessions.some((s) => s.session_id === sessionId)) return;
    sessions.unshift({
      session_id: sessionId,
      title:
        firstMessage.slice(0, 80) || `Conversation ${sessionId.slice(0, 8)}`,
      created_at: new Date().toISOString(),
    });
    // Keep last 20
    localStorage.setItem(
      'chat_sessions',
      JSON.stringify(sessions.slice(0, 20)),
    );
  } catch {
    // best-effort
  }
}

export async function closeChatSession(
  apiUrl: string,
  sessionId: string,
): Promise<void> {
  try {
    await fetch(`${apiUrl}/chat/sessions/${sessionId}/close`, {
      method: 'POST',
    });
  } catch {
    // best-effort
  }
}

interface StoredMessage {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: string;
  marketData?: any;
  sources?: any;
}

export function saveMessagesForSession(
  sessionId: string,

  messages: {
    id: string;
    text: string;
    sender: 'user' | 'bot';
    timestamp: Date;
    marketData?: any;
    sources?: any;
  }[],
): void {
  try {
    const stored: StoredMessage[] = messages.map((m) => ({
      id: m.id,
      text: m.text,
      sender: m.sender,
      timestamp: m.timestamp.toISOString(),
      ...(m.marketData ? { marketData: m.marketData } : {}),
      ...(m.sources ? { sources: m.sources } : {}),
    }));
    localStorage.setItem(`chat_msgs_${sessionId}`, JSON.stringify(stored));
  } catch {
    // best-effort
  }
}

export function loadMessagesForSession(sessionId: string): {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: Date;
  marketData?: any;
  sources?: any;
}[] {
  try {
    const raw = localStorage.getItem(`chat_msgs_${sessionId}`);
    if (!raw) return [];
    const stored: StoredMessage[] = JSON.parse(raw);
    return stored.map((m) => ({
      id: m.id,
      text: m.text,
      sender: m.sender,
      timestamp: new Date(m.timestamp),
      ...(m.marketData ? { marketData: m.marketData } : {}),
      ...(m.sources ? { sources: m.sources } : {}),
    }));
  } catch {
    return [];
  }
}
