import { useEffect, useState, type RefObject } from 'react';
import { Spinner } from '../spinner';

interface Props {
  containerRef: RefObject<HTMLDivElement | null>;
  loading: boolean;
  loadingMessage: string;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitView: () => void;
}

const ControlBtn = ({
  onClick,
  title,
  children,
}: {
  onClick: () => void;
  title: string;
  children: React.ReactNode;
}) => (
  <button
    onClick={onClick}
    title={title}
    className="w-8 h-8 flex items-center justify-center bg-white border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-colors first:rounded-t-lg last:rounded-b-lg border-b-0 last:border-b"
  >
    {children}
  </button>
);

export function GraphCanvas({
  containerRef,
  loading,
  loadingMessage,
  onZoomIn,
  onZoomOut,
  onFitView,
}: Props) {
  const [visReady, setVisReady] = useState(!!(window as any).vis);

  useEffect(() => {
    if ((window as any).vis) {
      setVisReady(true);
      return;
    }
    const script = document.createElement('script');
    script.src =
      'https://unpkg.com/vis-network/standalone/umd/vis-network.min.js';
    script.async = true;
    script.onload = () => setVisReady(true);
    script.onerror = () => console.error('Failed to load vis-network');
    document.body.appendChild(script);
  }, []);

  useEffect(() => {
    if (document.querySelector('link[href*="font-awesome"]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href =
      'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css';
    document.head.appendChild(link);
  }, []);

  return (
    <main className="flex-1 relative min-w-0">
      <div ref={containerRef} className="w-full h-full bg-slate-50" />

      {/* Floating zoom controls */}
      <div className="absolute bottom-4 right-4 z-20 flex flex-col shadow-sm rounded-lg">
        <ControlBtn onClick={onZoomIn} title="Zoom in">
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M7 3v8M3 7h8" />
          </svg>
        </ControlBtn>
        <ControlBtn onClick={onZoomOut} title="Zoom out">
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M3 7h8" />
          </svg>
        </ControlBtn>
        <ControlBtn onClick={onFitView} title="Fit to screen">
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <rect x="2" y="2" width="10" height="10" rx="1" />
            <path d="M5 7h4M7 5v4" />
          </svg>
        </ControlBtn>
      </div>

      {(loading || !visReady) && (
        <div className="absolute inset-0 bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center z-10">
          <Spinner />
          <p className="mt-3 text-slate-400 text-sm">{loadingMessage}</p>
        </div>
      )}
    </main>
  );
}
