import { useState, type ReactNode } from 'react';
import type { Screen } from './types';
import { TAB_SCREEN_NAMES } from './types';
import { useBook } from './hooks/useBook';
import { useReview } from './hooks/useReview';
import { Shell } from './components/shell/Shell';
import { SearchIcon } from './icons';
import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';
import { OnboardingPage } from './pages/OnboardingPage';
import { HomePage } from './pages/HomePage';
import { SearchPage } from './pages/SearchPage';
import { BoardPage } from './pages/BoardPage';
import { BookDetailPage } from './pages/BookDetailPage';
import { ReviewWritePage } from './pages/ReviewWritePage';
import { ReviewDetailPage } from './pages/ReviewDetailPage';
import { MyPage } from './pages/MyPage';

export function App() {
  const [authed, setAuthed] = useState(false);
  const [onboardingComplete, setOnboardingComplete] = useState(false);
  const [screen, setScreen] = useState<Screen>({ name: 'login' });
  const [history, setHistory] = useState<Screen[]>([]);

  const navigate = (next: Screen) => {
    setHistory((h) => [...h, screen]);
    setScreen(next);
  };

  // 히스토리에 새로 쌓지 않고 현재 화면을 교체한다 — 제출 후 결과 화면으로 넘어갈 때
  // 뒤로가기가 이미 끝난 입력 화면(예: 리뷰 작성 폼)으로 돌아가지 않도록 하기 위함.
  const replace = (next: Screen) => {
    setScreen(next);
  };

  const goBack = () => {
    setHistory((h) => {
      if (h.length === 0) {
        setScreen({ name: 'home' });
        return h;
      }
      setScreen(h[h.length - 1]);
      return h.slice(0, -1);
    });
  };

  const bookDetailId = screen.name === 'bookDetail' ? screen.bookId : '';
  const { data: headerBook, isLoading: headerBookLoading } = useBook(bookDetailId);

  const reviewDetailId = screen.name === 'reviewDetail' ? screen.reviewId : '';
  const { data: headerReview } = useReview(reviewDetailId);
  const { data: headerReviewBook, isLoading: headerReviewBookLoading } = useBook(
    headerReview?.bookId ?? '',
  );

  if (!authed) {
    if (screen.name === 'signup') {
      return (
        <SignupPage
          onSignupComplete={() => {
            setAuthed(true);
            setScreen({ name: 'onboarding' });
          }}
          onBack={() => setScreen({ name: 'login' })}
        />
      );
    }
    return (
      <LoginPage
        onLogin={() => {
          setAuthed(true);
          setScreen({ name: 'onboarding' });
        }}
        onGoSignup={() => setScreen({ name: 'signup' })}
      />
    );
  }

  if (!onboardingComplete) {
    return (
      <OnboardingPage
        onComplete={() => {
          setOnboardingComplete(true);
          setScreen({ name: 'home' });
        }}
      />
    );
  }

  const showBottomNav = TAB_SCREEN_NAMES.includes(screen.name);
  const activeTab = TAB_SCREEN_NAMES.includes(screen.name) ? screen.name : 'home';

  let title = '결';
  let onBack: (() => void) | undefined;
  let rightSlot: ReactNode;

  switch (screen.name) {
    case 'home':
      title = '결';
      rightSlot = (
        <button
          type="button"
          onClick={() => navigate({ name: 'search' })}
          aria-label="검색"
          style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex' }}
        >
          <SearchIcon width={20} height={20} />
        </button>
      );
      break;
    case 'board':
      title = '게시판';
      break;
    case 'search':
      title = '검색';
      break;
    case 'mypage':
      title = '마이페이지';
      break;
    case 'bookDetail':
      title = headerBookLoading ? '' : (headerBook?.title ?? '책 상세');
      onBack = goBack;
      break;
    case 'reviewWrite':
      title = '기록 남기기';
      onBack = goBack;
      break;
    case 'reviewDetail':
      title = headerReviewBookLoading ? '' : (headerReviewBook?.title ?? '리뷰 상세');
      onBack = goBack;
      break;
  }

  return (
    <Shell
      title={title}
      onBack={onBack}
      rightSlot={rightSlot}
      showBottomNav={showBottomNav}
      activeTab={activeTab}
      onNavigateTab={(name) => {
        if (name === 'home') navigate({ name: 'home' });
        else if (name === 'board') navigate({ name: 'board' });
        else if (name === 'search') navigate({ name: 'search' });
        else navigate({ name: 'mypage' });
      }}
    >
      {screen.name === 'home' && (
        <HomePage onSelectBook={(bookId) => navigate({ name: 'bookDetail', bookId })} />
      )}

      {screen.name === 'search' && (
        <SearchPage onSelectBook={(bookId) => navigate({ name: 'bookDetail', bookId })} />
      )}

      {screen.name === 'board' && (
        <BoardPage
          onSelectReview={(reviewId) => navigate({ name: 'reviewDetail', reviewId })}
          onWriteReview={() => navigate({ name: 'reviewWrite', bookId: '' })}
        />
      )}

      {screen.name === 'mypage' && (
        <MyPage
          onSelectBook={(bookId) => navigate({ name: 'bookDetail', bookId })}
          onSelectReview={(reviewId) => navigate({ name: 'reviewDetail', reviewId })}
        />
      )}

      {screen.name === 'bookDetail' && (
        <BookDetailPage
          bookId={screen.bookId}
          onSelectReview={(reviewId) => navigate({ name: 'reviewDetail', reviewId })}
          onWriteReview={(bookId) => navigate({ name: 'reviewWrite', bookId })}
        />
      )}

      {screen.name === 'reviewWrite' && (
        <ReviewWritePage
          bookId={screen.bookId}
          onCreated={(reviewId) => replace({ name: 'reviewDetail', reviewId })}
        />
      )}

      {screen.name === 'reviewDetail' && (
        <ReviewDetailPage
          reviewId={screen.reviewId}
          onSelectBook={(bookId) => navigate({ name: 'bookDetail', bookId })}
        />
      )}
    </Shell>
  );
}
