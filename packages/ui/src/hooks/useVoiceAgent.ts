import { useState, useRef, useCallback, useEffect } from 'react';
import { fromCognitoIdentityPool } from '@aws-sdk/credential-providers';
import { Sha256 } from '@aws-crypto/sha256-js';
import { SignatureV4 } from '@smithy/signature-v4';

export interface ConversationTurn {
  role: 'user' | 'assistant';
  transcript: string;
  timestamp: Date;
}

export interface UseVoiceAgentReturn {
  isConnected: boolean;
  isRecording: boolean;
  isSpeaking: boolean;
  isMuted: boolean;
  isThinking: boolean;
  thinkingStatus: string | null;
  error: string | null;
  conversationHistory: ConversationTurn[];
  userTranscript: string;
  agentTranscript: string;
  connect: () => Promise<void>;
  disconnect: () => void;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  toggleMute: () => void;
}

export interface UseVoiceAgentOptions {
  voiceGatewayArn?: string;
  region?: string;
  accessToken?: string;
  identityPoolId?: string;
  userPoolId?: string;
}

async function createPresignedWsUrl(
  arn: string,
  region: string,
  identityPoolId: string,
  userPoolId: string,
  idToken: string,
): Promise<string> {
  const creds = await fromCognitoIdentityPool({
    identityPoolId,
    logins: {
      [`cognito-idp.${region}.amazonaws.com/${userPoolId}`]: idToken,
    },
    clientConfig: { region },
  })();

  const signer = new SignatureV4({
    service: 'bedrock-agentcore',
    region,
    credentials: creds,
    sha256: Sha256,
  });

  const host = `bedrock-agentcore.${region}.amazonaws.com`;
  const path = `/runtimes/${arn}/ws`;

  const signed = await signer.presign(
    {
      method: 'GET',
      protocol: 'wss:',
      hostname: host,
      path,
      headers: { host },
      query: { qualifier: 'DEFAULT' },
    },
    { expiresIn: 300 },
  );

  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(signed.query ?? {})) {
    params.set(k, String(v));
  }
  return `wss://${host}${signed.path}?${params.toString()}`;
}

export function useVoiceAgent(
  opts?: UseVoiceAgentOptions,
): UseVoiceAgentReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [thinkingStatus, setThinkingStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conversationHistory, setConversationHistory] = useState<
    ConversationTurn[]
  >([]);
  const [userTranscript, setUserTranscript] = useState('');
  const [agentTranscript, setAgentTranscript] = useState('');

  const wsRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<{ stop: () => void; stream: MediaStream } | null>(
    null,
  );
  const recCtxRef = useRef<AudioContext | null>(null);
  const playCtxRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<AudioBuffer[]>([]);
  const playingRef = useRef(false);
  const mutedRef = useRef(false);

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      mutedRef.current = !prev;
      if (!prev) {
        audioQueueRef.current = [];
        playingRef.current = false;
        setIsSpeaking(false);
      }
      return !prev;
    });
  }, []);

  // --- audio playback ---
  const playNext = useCallback(() => {
    if (!audioQueueRef.current.length) {
      playingRef.current = false;
      setIsSpeaking(false);
      return;
    }
    if (!playCtxRef.current || playCtxRef.current.state === 'closed') {
      audioQueueRef.current = [];
      playingRef.current = false;
      setIsSpeaking(false);
      return;
    }
    playingRef.current = true;
    setIsSpeaking(true);
    const buf = audioQueueRef.current.shift()!;
    const src = playCtxRef.current.createBufferSource();
    src.buffer = buf;
    src.connect(playCtxRef.current.destination);
    src.onended = playNext;
    src.start();
  }, []);

  const queueAudio = useCallback(
    (b64: string, sampleRate: number) => {
      if (mutedRef.current) return;
      try {
        if (!playCtxRef.current || playCtxRef.current.state === 'closed') {
          playCtxRef.current = new AudioContext({ sampleRate });
        }
        const bin = atob(b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        const pcm = new Int16Array(bytes.buffer);
        const floats = new Float32Array(pcm.length);
        for (let i = 0; i < pcm.length; i++)
          floats[i] = pcm[i] / (pcm[i] < 0 ? 0x8000 : 0x7fff);
        const ab = playCtxRef.current.createBuffer(
          1,
          floats.length,
          sampleRate,
        );
        ab.getChannelData(0).set(floats);
        audioQueueRef.current.push(ab);
        if (!playingRef.current) playNext();
      } catch (e) {
        console.error('Audio queue error:', e);
      }
    },
    [playNext],
  );

  // --- websocket ---
  const connect = useCallback(async () => {
    setError(null);
    let url: string;

    const envUrl = (import.meta as any).env.VITE_VOICE_GATEWAY_URL;
    if (envUrl) {
      url = `${envUrl.replace(/\/+$/, '')}/ws`;
    } else if (
      opts?.voiceGatewayArn &&
      opts?.region &&
      opts?.identityPoolId &&
      opts?.userPoolId &&
      opts?.accessToken
    ) {
      try {
        url = await createPresignedWsUrl(
          opts.voiceGatewayArn,
          opts.region,
          opts.identityPoolId,
          opts.userPoolId,
          opts.accessToken,
        );
      } catch (e: any) {
        setError(`Auth error: ${e.message}`);
        return;
      }
    } else {
      url = 'ws://localhost:9005/ws';
    }

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => {
      setIsConnected(false);
      setIsRecording(false);
      setIsSpeaking(false);
    };
    ws.onerror = () => setError('WebSocket connection failed');

    ws.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        if (d.type !== 'bidi_audio_stream') {
          console.log('[voice] event:', d.type, d);
        }
        if (d.type === 'bidi_audio_stream' && d.audio) {
          queueAudio(d.audio, d.sample_rate || 16000);
        } else if (d.type === 'bidi_transcript_stream') {
          const role =
            d.role === 'user' ? ('user' as const) : ('assistant' as const);
          const isFinal = d.is_final !== false;
          console.log(
            '[voice]',
            role,
            isFinal ? 'FINAL' : 'partial',
            JSON.stringify(d.text),
          );
          if (role === 'assistant') {
            setIsThinking(false);
            setThinkingStatus(null);
            if (!isFinal && d.text) {
              setAgentTranscript((prev) => prev + d.text);
            }
            setIsSpeaking(true);
          } else {
            if (isFinal && d.text) {
              setAgentTranscript((prev) => {
                if (prev.trim()) {
                  setConversationHistory((h) => [
                    ...h,
                    {
                      role: 'assistant',
                      transcript: prev.trim(),
                      timestamp: new Date(),
                    },
                  ]);
                }
                return '';
              });
              setUserTranscript('');
              setIsThinking(true);
              setThinkingStatus('Thinking…');
              setConversationHistory((prev) => [
                ...prev,
                { role: 'user', transcript: d.text, timestamp: new Date() },
              ]);
            } else {
              setUserTranscript(d.text || '');
            }
          }
        } else if (d.type === 'bidi_interruption') {
          audioQueueRef.current = [];
          playingRef.current = false;
          setIsSpeaking(false);
        } else if (d.type === 'tool_use_stream') {
          const toolName = d.current_tool_use?.name || '';
          const label = toolName.includes('database')
            ? 'Querying client data…'
            : toolName.includes('stock')
              ? 'Fetching stock data…'
              : toolName.includes('web') || toolName.includes('search')
                ? 'Searching the web…'
                : 'Calling specialist agent…';
          setThinkingStatus(label);
        } else if (d.type === 'tool_result') {
          setThinkingStatus('Generating response…');
        }
      } catch {
        /* ignore */
      }
    };

    await new Promise<void>((res, rej) => {
      ws.addEventListener('open', () => res(), { once: true });
      ws.addEventListener(
        'error',
        () => rej(new Error('WebSocket connection failed')),
        { once: true },
      );
    });
  }, [opts, queueAudio]);

  const disconnect = useCallback(() => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
    audioQueueRef.current = [];
    playingRef.current = false;
    recCtxRef.current?.close();
    playCtxRef.current?.close();
    setIsConnected(false);
    setIsRecording(false);
    setIsSpeaking(false);
  }, []);

  // --- recording ---
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      const ctx = new AudioContext({ sampleRate: 16000 });
      recCtxRef.current = ctx;
      await ctx.audioWorklet.addModule('/audio-processor.worklet.js');
      const source = ctx.createMediaStreamSource(stream);
      const worklet = new AudioWorkletNode(ctx, 'audio-capture-processor');

      worklet.port.onmessage = (e) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN)
          return;
        if (e.data.type === 'audio') {
          const pcm = e.data.data as Int16Array;
          const b64 = btoa(String.fromCharCode(...new Uint8Array(pcm.buffer)));
          wsRef.current.send(
            JSON.stringify({
              type: 'bidi_audio_input',
              audio: b64,
              format: 'pcm',
              sample_rate: 16000,
              channels: 1,
            }),
          );
        }
      };

      source.connect(worklet);
      worklet.connect(ctx.destination);

      recorderRef.current = {
        stop: () => {
          worklet.disconnect();
          source.disconnect();
          ctx.close();
          stream.getTracks().forEach((t) => t.stop());
        },
        stream,
      };
      setIsRecording(true);
      setUserTranscript('');
    } catch (e: any) {
      setError(`Microphone error: ${e.message}`);
    }
  }, []);

  const stopRecording = useCallback(() => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setIsRecording(false);
  }, []);

  useEffect(
    () => () => {
      disconnect();
    },
    [disconnect],
  );

  return {
    isConnected,
    isRecording,
    isSpeaking,
    isMuted,
    isThinking,
    thinkingStatus,
    error,
    conversationHistory,
    userTranscript,
    agentTranscript,
    connect,
    disconnect,
    startRecording,
    stopRecording,
    toggleMute,
  };
}
