import { createContext, useContext, useState, useMemo, type ReactNode } from 'react';
import type { Review, UserProfile } from '../types';
import { reviews as initialReviews } from '../mock/reviews';
import { initialUserProfile } from '../mock/userProfile';

interface MockStoreValue {
  userProfile: UserProfile;
  updateUserProfile: (partial: Partial<UserProfile>) => void;
  toggleLikedBook: (bookId: string) => void;
  reviews: Review[];
  addReview: (review: Review) => void;
}

const MockStoreContext = createContext<MockStoreValue | null>(null);

export function MockStoreProvider({ children }: { children: ReactNode }) {
  const [userProfile, setUserProfile] = useState<UserProfile>(initialUserProfile);
  const [reviews, setReviews] = useState<Review[]>(initialReviews);

  const value = useMemo<MockStoreValue>(
    () => ({
      userProfile,
      updateUserProfile: (partial) => setUserProfile((prev) => ({ ...prev, ...partial })),
      toggleLikedBook: (bookId) =>
        setUserProfile((prev) => ({
          ...prev,
          likedBookIds: prev.likedBookIds.includes(bookId)
            ? prev.likedBookIds.filter((id) => id !== bookId)
            : [...prev.likedBookIds, bookId],
        })),
      reviews,
      addReview: (review) => setReviews((prev) => [review, ...prev]),
    }),
    [userProfile, reviews],
  );

  return <MockStoreContext.Provider value={value}>{children}</MockStoreContext.Provider>;
}

export function useMockStore(): MockStoreValue {
  const ctx = useContext(MockStoreContext);
  if (!ctx) {
    throw new Error('useMockStore must be used within a MockStoreProvider');
  }
  return ctx;
}
