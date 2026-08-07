export interface Book {
  id: string;
  title: string;
  author: string;
  publisher: string;
  coverUrl: string;
  synopsis: string;
  identityVectors: { trait: string; score: number; keywords: string[] }[];
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
