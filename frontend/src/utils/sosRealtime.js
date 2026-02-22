export const SOS_CHANGED_EVENT = 'aegis:sos-changed';

export const dispatchSosChangedEvent = (detail = {}) => {
  if (typeof window === 'undefined') {
    return;
  }
  window.dispatchEvent(
    new CustomEvent(SOS_CHANGED_EVENT, {
      detail: {
        at: new Date().toISOString(),
        ...detail,
      },
    }),
  );
};

export const buildSosEventsStreamUrl = () => {
  const base = (process.env.REACT_APP_API_URL || 'http://localhost:8001').replace(/\/+$/, '');
  return `${base}/api/sos/events/stream`;
};
