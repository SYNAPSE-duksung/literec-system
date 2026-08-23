import type { HookResult, SimilarReviewRecommendation } from '../types';
import { apiFetch } from '../lib/apiClient';
import { useAsyncApi } from './useAsyncApi';

export function useSimilarReviewBooks(reviewId: string): HookResult<SimilarReviewRecommendation[]> {
  return useAsyncApi(
    () =>
      reviewId
        ? apiFetch<SimilarReviewRecommendation[]>(
            `/api/reviews/${encodeURIComponent(reviewId)}/similar-books`,
          )
        : Promise.resolve([]),
    [reviewId],
    [],
  );
}
