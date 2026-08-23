export interface Book {
  id: string;
  title: string;
  author: string;
  publisher: string;
  coverUrl: string;
  synopsis: string;
  // trait/score 매핑(스코어링)은 미확정이라 현재 항상 빈 배열 — LiteRec_Backend_ClaudeCode_Brief.md §9.1
  identityVectors: { trait: string; score: number; keywords: string[] }[];
  // book_aspects 원본 축 텍스트(정서_경험/좋았던_요소/별로였던_요소) — 스코어링 없이 그대로 노출
  aspects: {
    emotionExperience: string[];
    likedElements: string[];
    dislikedElements: string[];
  };
}

export interface Review {
  id: string;
  bookId: string;
  userId: string;
  userName: string;
  content: string;
  liked: string[];
  disliked: string[];
  emotion: string[];
  likeCount: number;
  createdAt: string;
}

export interface Recommendation {
  bookId: string;
  hookLine: string;
  matchedTrait: string;
  explanation: string;
}

export interface UserProfile {
  userId: string;
  preferredEmotions: string[];
  avoidedTraits: string[];
  likedBookIds: string[];
}

export interface SimilarReviewRecommendation {
  sourceReviewId: string;
  bookId: string;
  matchedReviewSnippet: string;
  similarityReason: string;
}

export interface HookResult<T> {
  data: T;
  isLoading: boolean;
  isError: boolean;
}

export * from './screen';
