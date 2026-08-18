import type { Review } from '../types';
import { apiFetch } from '../lib/apiClient';

export interface UpdateReviewInput {
  content: string;
  liked: string[];
  disliked: string[];
  emotion: string[];
}

export interface UseUpdateReviewResult {
  updateReview: (reviewId: string, input: UpdateReviewInput) => Promise<Review>;
}

export function useUpdateReview(): UseUpdateReviewResult {
  const updateReview = (reviewId: string, input: UpdateReviewInput): Promise<Review> =>
    apiFetch<Review>(`/api/reviews/${reviewId}`, {
      method: 'PATCH',
      body: JSON.stringify({
        content: input.content,
        emotion: input.emotion,
        liked: input.liked,
        disliked: input.disliked,
      }),
    });

  return { updateReview };
}
