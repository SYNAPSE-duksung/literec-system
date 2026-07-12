import type { HookResult, Review } from '../types';
import { useMockStore } from '../state/MockStoreContext';
import { useAsyncMock } from './useAsyncMock';

export function useReviews(filter?: string): HookResult<Review[]> {
  const { reviews } = useMockStore();
  return useAsyncMock(() => {
    if (!filter || !filter.trim()) return reviews;
    const query = filter.trim().toLowerCase();
    return reviews.filter(
      (review) =>
        review.content.toLowerCase().includes(query) ||
        review.emotion.some((e) => e.toLowerCase().includes(query)),
    );
  }, [reviews, filter]);
}
