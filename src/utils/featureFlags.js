import { useState, useEffect } from 'react';

const ADVANCED_FEATURES_KEY = 'workloop-advanced-features';
const CHANGE_EVENT = 'advanced-features-changed';

export function getAdvancedFeatures() {
  try {
    return localStorage.getItem(ADVANCED_FEATURES_KEY) === 'true';
  } catch {
    return false;
  }
}

export function setAdvancedFeatures(enabled) {
  try {
    localStorage.setItem(ADVANCED_FEATURES_KEY, String(enabled));
    window.dispatchEvent(new Event(CHANGE_EVENT));
  } catch { /* ignore */ }
}

export function useAdvancedFeatures() {
  const [enabled, setEnabled] = useState(getAdvancedFeatures());

  useEffect(() => {
    const handler = () => setEnabled(getAdvancedFeatures());
    window.addEventListener(CHANGE_EVENT, handler);
    return () => window.removeEventListener(CHANGE_EVENT, handler);
  }, []);

  return enabled;
}
