import { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from ':wealth-management-portal/common-shadcn/components/ui/button';
import { Input } from ':wealth-management-portal/common-shadcn/components/ui/input';

interface Props {
  /** CSS selector or ref-based container where text selection triggers the tooltip */
  containerSelector: string;
  onSearch: (query: string) => void;
}

export function SelectionTooltip({ containerSelector, onSearch }: Props) {
  const [visible, setVisible] = useState(false);
  const [selectedText, setSelectedText] = useState('');
  const [query, setQuery] = useState('');
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const tooltipRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const hide = useCallback(() => {
    setVisible(false);
    setSelectedText('');
  }, []);

  const submit = useCallback(() => {
    if (!query.trim()) return;
    hide();
    onSearch(query.trim());
  }, [query, hide, onSearch]);

  useEffect(() => {
    const onMouseUp = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest(containerSelector)) return;

      const sel = window.getSelection();
      const text = sel?.toString().trim() || '';
      if (text.length < 2) return;

      const truncated = text.length > 500 ? text.slice(0, 499) + '...' : text;
      setSelectedText(truncated);
      setQuery(`Analyze "${truncated}" in more detail`);

      const range = sel!.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      let top = rect.bottom + 8;
      let left = rect.left;
      if (left + 330 > window.innerWidth) left = window.innerWidth - 340;
      if (left < 10) left = 10;
      if (top + 120 > window.innerHeight) top = rect.top - 120;

      setPosition({ top, left });
      setVisible(true);
      setTimeout(() => inputRef.current?.select(), 0);
    };

    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (
        !tooltipRef.current?.contains(target) &&
        !target.closest(containerSelector)
      ) {
        hide();
      }
    };

    document.addEventListener('mouseup', onMouseUp);
    document.addEventListener('mousedown', onMouseDown);
    return () => {
      document.removeEventListener('mouseup', onMouseUp);
      document.removeEventListener('mousedown', onMouseDown);
    };
  }, [containerSelector, hide]);

  if (!visible) return null;

  return (
    <div
      ref={tooltipRef}
      className="fixed z-[200] bg-white border border-blue-500 rounded-lg shadow-lg p-2.5 w-[320px] flex flex-col gap-1.5"
      style={{ top: position.top, left: position.left }}
    >
      <p className="text-xs text-gray-500 truncate">
        Selected: <strong className="text-blue-500">{selectedText}</strong>
      </p>
      <Input
        ref={inputRef}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') submit();
          if (e.key === 'Escape') hide();
        }}
        placeholder="Ask about this selection..."
        className="text-xs h-8"
      />
      <div className="flex justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          className="text-xs h-7"
          onClick={hide}
        >
          Cancel
        </Button>
        <Button size="sm" className="text-xs h-7" onClick={submit}>
          🔍 Ask
        </Button>
      </div>
    </div>
  );
}
