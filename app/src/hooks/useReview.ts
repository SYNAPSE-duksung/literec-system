import type { HookResult, Review } from '../types';
import { apiFetch } from '../lib/apiClient';
import { useAsyncApi } from './useAsyncApi';

export function useReview(reviewId: string): HookResult<Review | null> {
  return useAsyncApi<Review | null>(
    () =>
      reviewId ? apiFetch<Review>(`/api/reviews/${encodeURIComponent(reviewId)}`) : Promise.resolve(null),
    [reviewId],
    null,
  );
}
