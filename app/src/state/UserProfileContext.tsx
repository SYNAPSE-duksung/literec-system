import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import type { UserProfile } from '../types';
import { apiFetch } from '../lib/apiClient';

interface ProfileResponse {
  userId: string;
  preferredEmotions: string[];
  avoidedTraits: string[];
}

interface BookReactionsResponse {
  likedBookIds: string[];
  dislikedBookIds: string[];
}

interface UserProfileContextValue {
  data: UserProfile | null;
  isLoading: boolean;
  isError: boolean;
  dislikedBookIds: string[];
  updateProfile: (partial: Partial<UserProfile>) => Promise<void>;
  setBookReaction: (bookId: string, reaction: 'like' | 'dislike' | null) => void;
}

const UserProfileContext = createContext<UserProfileContextValue | null>(null);

// BookCard 등 여러 컴포넌트가 동시에 useUserProfile()을 호출하므로, 요청을 한 번만
// 보내고 결과를 공유하기 위해 Context로 감싼다(각자 독립적으로 fetch하면 화면에 보이는
// 책 카드 수만큼 /api/users/me/profile·book-reactions 요청이 중복 발생함).
export function UserProfileProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<UserProfile | null>(null);
  const [dislikedBookIds, setDislikedBookIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);

  const load = useCallback(() => {
    setIsLoading(true);
    setIsError(false);
    Promise.all([
      apiFetch<ProfileResponse>('/api/users/me/profile'),
      apiFetch<BookReactionsResponse>('/api/users/me/book-reactions'),
    ])
      .then(([profile, reactions]) => {
        setData({
          userId: profile.userId,
          preferredEmotions: profile.preferredEmotions,
          avoidedTraits: profile.avoidedTraits,
          likedBookIds: reactions.likedBookIds,
        });
        setDislikedBookIds(reactions.dislikedBookIds);
      })
      .catch(() => setIsError(true))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Promise를 반환한다 — 온보딩처럼 "저장이 끝난 뒤에 화면을 옮겨야" 하는
  // 호출부가 완료를 기다릴 수 있어야 한다(안 그러면 ML 프로필 등록이 끝나기 전에
  // 추천 조회가 먼저 나가 빈 추천으로 뜨는 레이스가 생긴다).
  const updateProfile = async (partial: Partial<UserProfile>): Promise<void> => {
    try {
      const profile = await apiFetch<ProfileResponse>('/api/users/me/profile', {
        method: 'PATCH',
        body: JSON.stringify({
          preferredEmotions: partial.preferredEmotions,
          avoidedTraits: partial.avoidedTraits,
        }),
      });
      setData((prev) => ({
        userId: profile.userId,
        preferredEmotions: profile.preferredEmotions,
        avoidedTraits: profile.avoidedTraits,
        likedBookIds: prev?.likedBookIds ?? [],
      }));
    } catch {
      setIsError(true);
    }
  };

  const setBookReaction = (bookId: string, reaction: 'like' | 'dislike' | null) => {
    const request =
      reaction === null
        ? apiFetch<void>(`/api/books/${encodeURIComponent(bookId)}/reaction`, { method: 'DELETE' })
        : apiFetch<void>(`/api/books/${encodeURIComponent(bookId)}/reaction`, {
            method: 'POST',
            body: JSON.stringify({ reaction }),
          });

    request
      .then(() => {
        setData((prev) =>
          prev
            ? {
                ...prev,
                likedBookIds:
                  reaction === 'like'
                    ? prev.likedBookIds.includes(bookId)
                      ? prev.likedBookIds
                      : [...prev.likedBookIds, bookId]
                    : prev.likedBookIds.filter((id) => id !== bookId),
              }
            : prev,
        );
        setDislikedBookIds((prev) =>
          reaction === 'dislike'
            ? prev.includes(bookId)
              ? prev
              : [...prev, bookId]
            : prev.filter((id) => id !== bookId),
        );
      })
      .catch(() => setIsError(true));
  };

  const value: UserProfileContextValue = {
    data,
    isLoading,
    isError,
    dislikedBookIds,
    updateProfile,
    setBookReaction,
  };

  return <UserProfileContext.Provider value={value}>{children}</UserProfileContext.Provider>;
}

export function useUserProfileContext(): UserProfileContextValue {
  const ctx = useContext(UserProfileContext);
  if (!ctx) {
    throw new Error('useUserProfileContext must be used within a UserProfileProvider');
  }
  return ctx;
}
