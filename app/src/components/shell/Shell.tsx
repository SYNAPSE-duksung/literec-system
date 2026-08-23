import { useEffect, useRef, type ReactNode } from 'react';
import type { ScreenName } from '../../types';
import { TopHeader } from './TopHeader';
import { BottomNav } from './BottomNav';

interface ShellProps {
  title: string;
  onBack?: () => void;
  rightSlot?: ReactNode;
  showBottomNav: boolean;
  activeTab: ScreenName;
  onNavigateTab: (name: 'home' | 'board' | 'search' | 'mypage') => void;
  // 화면이 바뀔 때마다 값이 달라지는 키 — 이전 화면의 스크롤 위치가 새 화면에 그대로
  // 남아있지 않도록 콘텐츠 스크롤을 맨 위로 되돌리는 데만 쓰인다.
  scrollKey: string;
  children: ReactNode;
}

export function Shell({
  title,
  onBack,
  rightSlot,
  showBottomNav,
  activeTab,
  onNavigateTab,
  scrollKey,
  children,
}: ShellProps) {
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    contentRef.current?.scrollTo(0, 0);
  }, [scrollKey]);

  return (
    <div className="app-shell">
      <TopHeader title={title} onBack={onBack} rightSlot={rightSlot} />
      <div className="app-shell__content" ref={contentRef}>
        {children}
      </div>
      {showBottomNav && <BottomNav active={activeTab} onNavigate={onNavigateTab} />}
    </div>
  );
}
