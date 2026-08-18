export type MyListType = 'likedBooks' | 'dislikedBooks' | 'myReviews';

export type Screen =
  | { name: 'login' }
  | { name: 'signup' }
  | { name: 'onboarding' }
  | { name: 'home' }
  | { name: 'bookDetail'; bookId: string }
  | { name: 'board' }
  | { name: 'reviewWrite'; bookId: string; reviewId?: string }
  | { name: 'reviewDetail'; reviewId: string }
  | { name: 'search' }
  | { name: 'mypage' }
  | { name: 'myList'; listType: MyListType };

export type ScreenName = Screen['name'];

export const TAB_SCREEN_NAMES: ScreenName[] = ['home', 'board', 'search', 'mypage'];
