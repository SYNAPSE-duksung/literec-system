import { apiFetch } from '../lib/apiClient';

export interface UseDeleteReviewResult {
  deleteReview: (reviewId: string) => Promise<void>;
}

export function useDeleteReview(): UseDeleteReviewResult {
  const deleteReview = (reviewId: string): Promise<void> =>
    apiFetch<void>(`/api/reviews/${reviewId}`, { method: 'DELETE' });

  return { deleteReview };
}
