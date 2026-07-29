import { createContext, useContext, useState, useMemo, type ReactNode } from 'react';
import type { Review, UserProfile } from '../types';
import { reviews as initialReviews } from '../mock/reviews';
import { initialUserProfile } from '../mock/userProfile';

type Reaction = 'like' | 'dislike' | null;

interface MockStoreValue {
  userProfile: UserProfile;
  updateUserProfile: (partial: Partial<UserProfile>) => void;
  dislikedBookIds: string[];
  setBookReaction: (bookId: string, reaction: Reaction) => void;
  reviews: Review[];
  addReview: (review: Review) => void;
  reviewReactions: Record<string, Reaction>;
  setReviewReaction: (reviewId: string, reaction: Reaction) => void;
}

const MockStoreContext = createContext<MockStoreValue | null>(null);

export function MockStoreProvider({ children }: { children: ReactNode }) {
  const [userProfile, setUserProfile] = useState<UserProfile>(initialUserProfile);
  const [dislikedBookIds, setDislikedBookIds] = useState<string[]>([]);
  const [reviews, setReviews] = useState<Review[]>(initialReviews);
  const [reviewReactions, setReviewReactions] = useState<Record<string, Reaction>>({});

  const value = useMemo<MockStoreValue>(() => {
    const setBookReaction = (bookId: string, reaction: Reaction) => {
      setUserProfile((prev) => ({
        ...prev,
        likedBookIds:
          reaction === 'like'
            ? prev.likedBookIds.includes(bookId)
              ? prev.likedBookIds
              : [...prev.likedBookIds, bookId]
            : prev.likedBookIds.filter((id) => id !== bookId),
      }));
      setDislikedBookIds((prev) =>
        reaction === 'dislike'
          ? prev.includes(bookId)
            ? prev
            : [...prev, bookId]
          : prev.filter((id) => id !== bookId),
      );
    };

    return {
      userProfile,
      updateUserProfile: (partial) => setUserProfile((prev) => ({ ...prev, ...partial })),
      dislikedBookIds,
      setBookReaction,
      reviews,
      addReview: (review) => setReviews((prev) => [review, ...prev]),
      reviewReactions,
      setReviewReaction: (reviewId, reaction) =>
        setReviewReactions((prev) => ({ ...prev, [reviewId]: reaction })),
    };
  }, [userProfile, dislikedBookIds, reviews, reviewReactions]);

  return <MockStoreContext.Provider value={value}>{children}</MockStoreContext.Provider>;
}

export function useMockStore(): MockStoreValue {
  const ctx = useContext(MockStoreContext);
  if (!ctx) {
    throw new Error('useMockStore must be used within a MockStoreProvider');
  }
  return ctx;
}
