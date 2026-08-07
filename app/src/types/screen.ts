export type Screen =
  | { name: 'login' }
  | { name: 'signup' }
  | { name: 'onboarding' }
  | { name: 'home' }
  | { name: 'bookDetail'; bookId: string }
  | { name: 'board' }
  | { name: 'reviewWrite'; bookId: string }
  | { name: 'reviewDetail'; reviewId: string }
  | { name: 'search' }
  | { name: 'mypage' };

export type ScreenName = Screen['name'];

export const TAB_SCREEN_NAMES: ScreenName[] = ['home', 'board', 'search', 'mypage'];
