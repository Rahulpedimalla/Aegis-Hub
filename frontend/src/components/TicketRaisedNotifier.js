import { useEffect, useRef } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';
import { buildSosEventsStreamUrl, dispatchSosChangedEvent } from '../utils/sosRealtime';

const POLL_INTERVAL_MS = 15000;
const STREAM_RECONNECT_MS = 4000;
const MAX_TRACKED_IDS = 500;

const sleep = (ms) =>
  new Promise((resolve) => {
    if (typeof window === 'undefined') {
      resolve();
      return;
    }
    window.setTimeout(resolve, ms);
  });

const ticketFingerprint = (ticket) =>
  [
    ticket?.id || '',
    ticket?.updated_at || '',
    ticket?.status || '',
    ticket?.assigned_to || '',
    ticket?.assigned_organization || '',
    ticket?.assigned_division || '',
  ].join('|');

const trackedSnapshot = (tickets) => {
  const ordered = [...tickets].sort(
    (a, b) => new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime(),
  );
  const limited = ordered.slice(-MAX_TRACKED_IDS);
  const map = new Map();
  limited.forEach((ticket) => {
    if (ticket?.id) {
      map.set(ticket.id, ticketFingerprint(ticket));
    }
  });
  return { ordered, map };
};

const TicketRaisedNotifier = () => {
  const { isAuthenticated, user } = useAuth();
  const initializedRef = useRef(false);
  const seenStateRef = useRef(new Map());

  useEffect(() => {
    initializedRef.current = false;
    seenStateRef.current = new Map();
  }, [isAuthenticated, user?.role, user?.username]);

  useEffect(() => {
    if (!isAuthenticated || !user || !['admin', 'responder'].includes(user.role)) {
      return undefined;
    }

    let disposed = false;
    let streamController = null;
    let fallbackTimer = null;

    const load = async ({ forceDispatch = false } = {}) => {
      try {
        const response = await axios.get('/api/sos/?limit=250');
        const tickets = Array.isArray(response.data) ? response.data : [];
        const { ordered, map: nextState } = trackedSnapshot(tickets);

        if (!initializedRef.current) {
          initializedRef.current = true;
          seenStateRef.current = nextState;
          if (forceDispatch) {
            dispatchSosChangedEvent({ source: 'bootstrap' });
          }
          return;
        }

        const previousState = seenStateRef.current;
        const newTickets = ordered.filter((ticket) => ticket.id && !previousState.has(ticket.id));
        const changedTickets = ordered.filter((ticket) => {
          if (!ticket?.id || !previousState.has(ticket.id)) {
            return false;
          }
          return previousState.get(ticket.id) !== ticketFingerprint(ticket);
        });

        if (newTickets.length > 0) {
          toast.success(
            `${newTickets.length} Ticket${newTickets.length > 1 ? 's' : ''} raised`,
            { id: `ticket-raised-${user.role}` },
          );
        }
        if (changedTickets.length > 0) {
          toast.success(
            `${changedTickets.length} Ticket${changedTickets.length > 1 ? 's' : ''} updated`,
            { id: `ticket-updated-${user.role}` },
          );
        }

        const hasChanges = newTickets.length > 0 || changedTickets.length > 0;
        if (hasChanges || forceDispatch) {
          dispatchSosChangedEvent({
            source: forceDispatch ? 'stream' : 'poll',
            new_count: newTickets.length,
            updated_count: changedTickets.length,
          });
        }

        seenStateRef.current = nextState;
      } catch (error) {
        // Silent polling; no toast noise on transient issues.
      }
    };

    const connectStream = async () => {
      if (
        disposed ||
        typeof window === 'undefined' ||
        typeof window.fetch !== 'function' ||
        typeof window.ReadableStream === 'undefined'
      ) {
        return;
      }

      while (!disposed) {
        const token = window.localStorage.getItem('token');
        if (!token) {
          await sleep(STREAM_RECONNECT_MS);
          continue;
        }

        streamController = new AbortController();
        try {
          const response = await window.fetch(buildSosEventsStreamUrl(), {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${token}`,
              Accept: 'text/event-stream',
              'Cache-Control': 'no-cache',
            },
            signal: streamController.signal,
          });

          if (!response.ok || !response.body) {
            throw new Error(`SSE stream unavailable (${response.status})`);
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder('utf-8');
          let buffer = '';
          let eventName = '';
          let dataLines = [];

          while (!disposed) {
            const { done, value } = await reader.read();
            if (done) {
              break;
            }

            buffer += decoder.decode(value, { stream: true });
            let newlineIndex = buffer.indexOf('\n');

            while (newlineIndex !== -1) {
              let line = buffer.slice(0, newlineIndex);
              buffer = buffer.slice(newlineIndex + 1);
              if (line.endsWith('\r')) {
                line = line.slice(0, -1);
              }

              if (!line) {
                const eventType = (eventName || '').trim();
                const dataPayload = dataLines.join('\n').trim();

                if (eventType === 'tickets_changed') {
                  void load({ forceDispatch: true });
                } else if (dataPayload) {
                  try {
                    const parsed = JSON.parse(dataPayload);
                    if (parsed?.type === 'tickets_changed') {
                      void load({ forceDispatch: true });
                    }
                  } catch (_) {
                    // Ignore malformed event payloads.
                  }
                }

                eventName = '';
                dataLines = [];
                newlineIndex = buffer.indexOf('\n');
                continue;
              }

              if (line.startsWith(':')) {
                newlineIndex = buffer.indexOf('\n');
                continue;
              }

              if (line.startsWith('event:')) {
                eventName = line.slice(6).trim();
              } else if (line.startsWith('data:')) {
                dataLines.push(line.slice(5).trimStart());
              }

              newlineIndex = buffer.indexOf('\n');
            }
          }
        } catch (error) {
          if (disposed || error?.name === 'AbortError') {
            break;
          }
        } finally {
          streamController = null;
        }

        if (!disposed) {
          await sleep(STREAM_RECONNECT_MS);
        }
      }
    };

    load();
    void connectStream();
    fallbackTimer = window.setInterval(() => load(), POLL_INTERVAL_MS);

    return () => {
      disposed = true;
      if (streamController) {
        streamController.abort();
      }
      if (fallbackTimer) {
        window.clearInterval(fallbackTimer);
      }
    };
  }, [isAuthenticated, user]);

  return null;
};

export default TicketRaisedNotifier;
