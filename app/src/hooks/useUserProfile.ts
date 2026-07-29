import type { HookResult, UserProfile } from '../types';
import { useMockStore } from '../state/MockStoreContext';
import { useAsyncMock } from './useAsyncMock';

export interface UseUserProfileResult extends HookResult<UserProfile | null> {
  updateProfile: (partial: Partial<UserProfile>) => void;
  dislikedBookIds: string[];
  setBookReaction: (bookId: string, reaction: 'like' | 'dislike' | null) => void;
}

export function useUserProfile(): UseUserProfileResult {
  const { userProfile, updateUserProfile, dislikedBookIds, setBookReaction } = useMockStore();
  const result = useAsyncMock<UserProfile | null>(() => userProfile, [userProfile]);
  return { ...result, updateProfile: updateUserProfile, dislikedBookIds, setBookReaction };
}
