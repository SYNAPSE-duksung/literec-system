import { useEffect, useState } from 'react';
import { apiFetch } from '../lib/apiClient';

type Reaction = 'like' | 'dislike' | null;

export interface UseReviewReactionResult {
  myReaction: Reaction;
  setReaction: (reaction: Reaction) => void;
}

export function useReviewReaction(reviewId: string): UseReviewReactionResult {
  const [myReaction, setMyReaction] = useState<Reaction>(null);

  useEffect(() => {
    if (!reviewId) return;
    let cancelled = false;
    apiFetch<Record<string, 'like' | 'dislike'>>('/api/users/me/review-reactions')
      .then((reactions) => {
        if (!cancelled) setMyReaction(reactions[reviewId] ?? null);
      })
      .catch(() => {
        if (!cancelled) setMyReaction(null);
      });
    return () => {
      cancelled = true;
    };
  }, [reviewId]);

  const setReaction = (reaction: Reaction) => {
    const request =
      reaction === null
        ? apiFetch<void>(`/api/reviews/${encodeURIComponent(reviewId)}/reaction`, { method: 'DELETE' })
        : apiFetch<void>(`/api/reviews/${encodeURIComponent(reviewId)}/reaction`, {
            method: 'POST',
            body: JSON.stringify({ reaction }),
          });

    request.then(() => setMyReaction(reaction)).catch(() => {});
  };

  return { myReaction, setReaction };
}
