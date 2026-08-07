import type { HookResult, UserProfile } from '../types';
import { useUserProfileContext } from '../state/UserProfileContext';

export interface UseUserProfileResult extends HookResult<UserProfile | null> {
  updateProfile: (partial: Partial<UserProfile>) => void;
  dislikedBookIds: string[];
  setBookReaction: (bookId: string, reaction: 'like' | 'dislike' | null) => void;
}

export function useUserProfile(): UseUserProfileResult {
  const { data, isLoading, isError, dislikedBookIds, updateProfile, setBookReaction } =
    useUserProfileContext();
  return { data, isLoading, isError, dislikedBookIds, updateProfile, setBookReaction };
}
