import type { HookResult, Review } from '../types';
import { apiFetch } from '../lib/apiClient';
import { useAsyncApi } from './useAsyncApi';

export function useReviews(filter?: string): HookResult<Review[]> {
  return useAsyncApi(
    () => {
      const trimmed = filter?.trim();
      const query = trimmed ? `?filter=${encodeURIComponent(trimmed)}` : '';
      return apiFetch<Review[]>(`/api/reviews${query}`);
    },
    [filter],
    [],
  );
}
