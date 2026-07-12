import type { HookResult, Review } from '../types';
import { useMockStore } from '../state/MockStoreContext';
import { useAsyncMock } from './useAsyncMock';

export function useReview(reviewId: string): HookResult<Review | null> {
  const { reviews } = useMockStore();
  return useAsyncMock<Review | null>(
    () => reviews.find((review) => review.id === reviewId) ?? null,
    [reviews, reviewId],
  );
}
