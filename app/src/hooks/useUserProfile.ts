import type { HookResult, UserProfile } from '../types';
import { useMockStore } from '../state/MockStoreContext';
import { useAsyncMock } from './useAsyncMock';

export interface UseUserProfileResult extends HookResult<UserProfile | null> {
  updateProfile: (partial: Partial<UserProfile>) => void;
  toggleLikedBook: (bookId: string) => void;
}

export function useUserProfile(): UseUserProfileResult {
  const { userProfile, updateUserProfile, toggleLikedBook } = useMockStore();
  const result = useAsyncMock<UserProfile | null>(() => userProfile, [userProfile]);
  return { ...result, updateProfile: updateUserProfile, toggleLikedBook };
}
