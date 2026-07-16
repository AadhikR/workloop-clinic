import { useState, useEffect } from 'react';
import { WifiOff } from 'lucide-react';

export default function OfflineBanner() {
  const [offline, setOffline] = useState(!navigator.onLine);

  useEffect(() => {
    const goOff = () => setOffline(true);
    const goOn = () => setOffline(false);
    window.addEventListener('offline', goOff);
    window.addEventListener('online', goOn);
    return () => {
      window.removeEventListener('offline', goOff);
      window.removeEventListener('online', goOn);
    };
  }, []);

  if (!offline) return null;

  return (
    <div role="alert" aria-live="assertive" style={{
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 9999,
      background: '#dc2626', color: '#fff',
      padding: '8px 16px', fontSize: 13, fontWeight: 600,
      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
    }}>
      <WifiOff size={14} aria-hidden="true" />
      You are offline — changes will not be saved until your connection is restored.
    </div>
  );
}
