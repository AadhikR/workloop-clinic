import { useEffect } from 'react';

/**
 * Runs `callback` when the Escape key is pressed. Use in modals for keyboard dismiss.
 * Pass `enabled = false` to disable temporarily (e.g. while a nested modal is open).
 */
export function useEscapeKey(callback, enabled = true) {
  useEffect(() => {
    if (!enabled || typeof callback !== 'function') return;
    const handler = (e) => {
      if (e.key === 'Escape') callback(e);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [callback, enabled]);
}
