import type { HookResult, SimilarReviewRecommendation } from '../types';
import { similarReviewRecommendations } from '../mock/similarReviewRecommendations';
import { useAsyncMock } from './useAsyncMock';

export function useSimilarReviewBooks(reviewId: string): HookResult<SimilarReviewRecommendation[]> {
  return useAsyncMock(
    () => similarReviewRecommendations.filter((row) => row.sourceReviewId === reviewId),
    [reviewId],
    500,
  );
}
