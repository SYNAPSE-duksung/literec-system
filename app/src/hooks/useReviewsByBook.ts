import type { HookResult, Review } from '../types';
import { apiFetch } from '../lib/apiClient';
import { useAsyncApi } from './useAsyncApi';

export function useReviewsByBook(bookId: string): HookResult<Review[]> {
  return useAsyncApi(
    () =>
      bookId
        ? apiFetch<Review[]>(`/api/books/${encodeURIComponent(bookId)}/reviews`)
        : Promise.resolve([]),
    [bookId],
    [],
  );
}
