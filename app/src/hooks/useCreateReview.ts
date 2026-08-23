import type { Review } from '../types';
import { apiFetch } from '../lib/apiClient';

export interface CreateReviewInput {
  bookId: string;
  content: string;
  liked: string[];
  disliked: string[];
  emotion: string[];
}

export interface UseCreateReviewResult {
  createReview: (input: CreateReviewInput) => Promise<Review>;
}

export function useCreateReview(): UseCreateReviewResult {
  const createReview = (input: CreateReviewInput): Promise<Review> =>
    apiFetch<Review>('/api/reviews', {
      method: 'POST',
      body: JSON.stringify({
        isbn: input.bookId,
        content: input.content,
        emotion: input.emotion,
        liked: input.liked,
        disliked: input.disliked,
      }),
    });

  return { createReview };
}
