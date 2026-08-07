import type { HookResult, Review } from '../types';
import { useMockStore } from '../state/MockStoreContext';
import { useAsyncMock } from './useAsyncMock';

export function useReviewsByBook(bookId: string): HookResult<Review[]> {
  const { reviews } = useMockStore();
  return useAsyncMock(
    () => reviews.filter((review) => review.bookId === bookId),
    [reviews, bookId],
  );
}
