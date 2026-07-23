import { useMockStore } from '../state/MockStoreContext';

export interface UseReviewReactionResult {
  myReaction: 'like' | 'dislike' | null;
  setReaction: (reaction: 'like' | 'dislike' | null) => void;
}

export function useReviewReaction(reviewId: string): UseReviewReactionResult {
  const { reviewReactions, setReviewReaction } = useMockStore();
  return {
    myReaction: reviewReactions[reviewId] ?? null,
    setReaction: (reaction) => setReviewReaction(reviewId, reaction),
  };
}
