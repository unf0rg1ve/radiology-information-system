import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuthStore } from '../stores/authStore';

const getWsUrl = (channel: string, token: string | null): string | null => {
  if (!token) return null;
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = import.meta.env.VITE_WS_URL || `${proto}//${window.location.host}`;
  return `${host}/api/ws?token=${encodeURIComponent(token)}&channel=${encodeURIComponent(channel)}`;
};

export type WsMessage = {
  channel: string;
  type: string;
  [key: string]: any;
};

export function useWebSocket(channel: string, onMessage: (msg: WsMessage) => void) {
  const token = useAuthStore((state) => state.token);
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const onMessageRef = useRef(onMessage);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const connect = useCallback(() => {
    const url = getWsUrl(channel, token);
    if (!url) return;

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessageRef.current(data);
      } catch (e) {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      // reconnect in 5 seconds
      reconnectTimeoutRef.current = window.setTimeout(connect, 5000);
    };

    ws.onerror = () => {
      // onclose will handle reconnect
    };
  }, [channel, token]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { connected };
}
