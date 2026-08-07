import type { Review } from '../types';
import { useMockStore } from '../state/MockStoreContext';
import { CURRENT_USER_ID } from '../constants/user';

export interface CreateReviewInput {
  bookId: string;
  content: string;
  liked: string[];
  disliked: string[];
  emotion: string[];
}

export interface UseCreateReviewResult {
  createReview: (input: CreateReviewInput) => Review;
}

export function useCreateReview(): UseCreateReviewResult {
  const { addReview } = useMockStore();

  const createReview = (input: CreateReviewInput): Review => {
    const review: Review = {
      id: `review_${Date.now()}`,
      bookId: input.bookId,
      userId: CURRENT_USER_ID,
      userName: '나',
      content: input.content,
      liked: input.liked,
      disliked: input.disliked,
      emotion: input.emotion,
      likeCount: 0,
      createdAt: new Date().toISOString(),
    };
    addReview(review);
    return review;
  };

  return { createReview };
}
