import { apiFetch } from '../lib/apiClient';

export interface RecommendationEventInput {
  bookId: string;
  eventType: 'impression' | 'click' | 'like' | 'review';
  source: 'home' | 'book_detail' | 'review_detail';
  rank?: number;
}

export interface UseLogEventResult {
  logEvent: (input: RecommendationEventInput) => void;
}

export function useLogEvent(): UseLogEventResult {
  const logEvent = (input: RecommendationEventInput) => {
    apiFetch('/api/events', {
      method: 'POST',
      body: JSON.stringify({
        book_id: input.bookId,
        event_type: input.eventType,
        source: input.source,
        rank: input.rank,
      }),
    }).catch(() => {}); // 로깅 실패가 화면 동작을 막지 않음
  };

  return { logEvent };
}
