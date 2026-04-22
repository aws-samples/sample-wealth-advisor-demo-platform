import type {
  GraphData,
  ServerConfig,
  EnrichedSearchResponse,
} from '../components/GraphSearch/types';
import { fromCognitoIdentityPool } from '@aws-sdk/credential-providers';
import type { AwsCredentialIdentity } from '@aws-sdk/types';
import { Sha256 } from '@aws-crypto/sha256-js';
import { SignatureV4 } from '@smithy/signature-v4';

/**
 * Graph Search API service.
 * Base URL is provided by the caller (from runtime config).
 */

let _base = 'http://localhost:8005';
let _getToken: (() => string | undefined) | null = null;
let _agentArn = '';
let _agentRegion = '';
let _identityPoolId = '';
let _userPoolId = '';

export function setGraphSearchBaseUrl(url: string) {
  _base = url.replace(/\/+$/, '');
}

export function setGraphSearchAuth(getToken: () => string | undefined) {
  _getToken = getToken;
}

export function setGraphSearchAgent(
  agentArn: string,
  region: string,
  identityPoolId: string,
  userPoolId: string,
) {
  _agentArn = agentArn;
  _agentRegion = region;
  _identityPoolId = identityPoolId;
  _userPoolId = userPoolId;
}

function getAgentCoreCreds(): (() => Promise<AwsCredentialIdentity>) | null {
  const idToken = _getToken?.();
  if (!_agentArn || !_identityPoolId || !idToken) return null;
  return fromCognitoIdentityPool({
    identityPoolId: _identityPoolId,
    logins: {
      [`cognito-idp.${_agentRegion}.amazonaws.com/${_userPoolId}`]: idToken,
    },
    clientConfig: { region: _agentRegion },
  });
}

function getBase() {
  return _base;
}

function authHeaders(): Record<string, string> {
  const token = _getToken?.();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchGraphConfig(): Promise<ServerConfig> {
  const res = await fetch(`${getBase()}/api/config`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Config fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchGraphData(limit: number): Promise<GraphData> {
  const res = await fetch(`${getBase()}/api/graph?limit=${limit}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Graph fetch failed: ${res.status}`);
  return res.json();
}

export async function loadDataToNeptune(): Promise<void> {
  const res = await fetch(`${getBase()}/api/graph/load`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error('Load failed');
}

/**
 * Enrich search results via the API (fast — no agent call, just Neptune + column explain).
 */
async function enrichViaApi(
  query: string,
  searchResult: Record<string, unknown>,
  graphData: {
    nodes: {
      id: string;
      label: string;
      type: string;
      properties: Record<string, unknown>;
    }[];
    edges: { source: string; target: string; label: string }[];
  },
): Promise<EnrichedSearchResponse> {
  const res = await fetch(`${getBase()}/api/enrich`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      query,
      search_result: searchResult,
      graph_data: graphData,
    }),
  });
  if (!res.ok) throw new Error(`Enrich failed: ${res.status}`);
  return res.json();
}

/**
 * Invoke AgentCore directly from the browser (no API Gateway timeout).
 * Falls back to SSE stream via API if agent client is unavailable.
 */
export async function enrichedSearchStream(
  query: string,
  graphData: {
    nodes: {
      id: string;
      label: string;
      type: string;
      properties: Record<string, unknown>;
    }[];
    edges: { source: string; target: string; label: string }[];
  },
  onStatus: (message: string) => void,
  onToken?: (text: string) => void,
  onMatch?: (matchingIds: string[]) => void,
): Promise<EnrichedSearchResponse> {
  const credsFn = getAgentCoreCreds();

  if (credsFn) {
    // Direct AgentCore invocation with SSE streaming
    const payload = JSON.stringify({ query, graph_data: graphData });
    const arnEncoded = encodeURIComponent(_agentArn);
    const url = `https://bedrock-agentcore.${_agentRegion}.amazonaws.com/runtimes/${arnEncoded}/invocations`;
    const sessionId = `graph-search-${crypto.randomUUID()}`;

    const signer = new SignatureV4({
      service: 'bedrock-agentcore',
      region: _agentRegion,
      credentials: credsFn,
      sha256: Sha256,
    });

    const signed = await signer.sign({
      method: 'POST',
      protocol: 'https:',
      hostname: `bedrock-agentcore.${_agentRegion}.amazonaws.com`,
      path: `/runtimes/${arnEncoded}/invocations`,
      headers: {
        'content-type': 'application/json',
        accept: 'text/event-stream',
        host: `bedrock-agentcore.${_agentRegion}.amazonaws.com`,
        'x-amz-bedrock-agentcore-runtime-session-id': sessionId,
      },
      body: payload,
    });

    const response = await fetch(url, {
      method: 'POST',
      headers: signed.headers as Record<string, string>,
      body: payload,
    });

    if (!response.ok) {
      const errText = await response.text();
      console.warn('AgentCore direct call failed:', response.status, errText);
      throw new Error(`AgentCore ${response.status}`);
    }

    const contentType = response.headers.get('content-type') || '';

    // SSE streaming path
    if (contentType.includes('text/event-stream') && response.body) {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      return new Promise((resolve, reject) => {
        function pump() {
          reader
            .read()
            .then(({ done, value }) => {
              if (done) {
                reject(new Error('Stream ended without result'));
                return;
              }
              buffer += decoder.decode(value, { stream: true });
              const lines = buffer.split('\n');
              buffer = lines.pop()!;

              let eventType = '';
              for (const line of lines) {
                if (line.startsWith('event: '))
                  eventType = line.slice(7).trim();
                else if (line.startsWith('data: ') && eventType) {
                  try {
                    const data = JSON.parse(line.slice(6));
                    if (eventType === 'status') onStatus(data.message);
                    else if (eventType === 'token') onToken?.(data.text);
                    else if (eventType === 'match')
                      onMatch?.(data.matching_ids);
                    else if (eventType === 'result') {
                      // Enrich via API after getting search result
                      onStatus('✨ Enriching results...');
                      enrichViaApi(query, data, graphData)
                        .then(resolve)
                        .catch(reject);
                      return;
                    }
                  } catch {
                    /* ignore malformed JSON */
                  }
                  eventType = '';
                }
              }
              pump();
            })
            .catch(reject);
        }
        pump();
      });
    }

    // JSON fallback — non-streaming response from AgentCore
    const resultText = await response.text();
    const searchResult = resultText
      ? JSON.parse(resultText)
      : { matching_ids: [], explanation: 'No response from agent' };

    onStatus('✨ Enriching results...');
    return enrichViaApi(query, searchResult, graphData);
  }

  // Fallback: SSE stream via API Gateway (original path)
  const res = await fetch(`${getBase()}/api/nl-search-enriched-stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ query, graph_data: graphData }),
  });
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  return new Promise((resolve, reject) => {
    function pump() {
      reader
        .read()
        .then(({ done, value }) => {
          if (done) {
            reject(new Error('Stream ended without result'));
            return;
          }
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop()!;

          let eventType = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) eventType = line.slice(7);
            else if (line.startsWith('data: ')) {
              const payload = JSON.parse(line.slice(6));
              if (eventType === 'status') onStatus(payload.message);
              else if (eventType === 'token') onToken?.(payload.text);
              else if (eventType === 'match') onMatch?.(payload.matching_ids);
              else if (eventType === 'result') {
                resolve(payload);
                return;
              }
            }
          }
          pump();
        })
        .catch(reject);
    }
    pump();
  });
}
