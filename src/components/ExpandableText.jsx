import { useCallback, useRef, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

export default function ExpandableText({ text, empty = '—', tone = 'default' }) {
  const [expanded, setExpanded] = useState(false);
  const [canExpand, setCanExpand] = useState(false);
  const observerRef = useRef(null);
  const value = String(text || '').trim();

  const measureContent = useCallback(node => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    if (!node) return;

    const checkOverflow = () => {
      const lineHeight = parseFloat(window.getComputedStyle(node).lineHeight) || 17;
      setCanExpand(node.scrollHeight > (lineHeight * 2) + 1);
    };

    checkOverflow();
    if (typeof ResizeObserver !== 'undefined') {
      observerRef.current = new ResizeObserver(checkOverflow);
      observerRef.current.observe(node);
    }
  }, []);

  if (!value) {
    return <span className="expandable-text-empty">{empty}</span>;
  }

  return (
    <div className={`expandable-text-box ${expanded ? 'expanded' : 'collapsed'} ${tone === 'danger' ? 'expandable-text-danger' : ''}`}>
      <div key={value} ref={measureContent} className="expandable-text-content">{value}</div>
      {canExpand && (
        <button
          type="button"
          className="expandable-text-toggle"
          onClick={() => setExpanded(current => !current)}
          aria-expanded={expanded}
        >
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          {expanded ? 'Collapse' : 'Expand'}
        </button>
      )}
    </div>
  );
}