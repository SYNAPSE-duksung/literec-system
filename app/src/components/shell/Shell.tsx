import type { ReactNode } from 'react';
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
  children: ReactNode;
}

export function Shell({
  title,
  onBack,
  rightSlot,
  showBottomNav,
  activeTab,
  onNavigateTab,
  children,
}: ShellProps) {
  return (
    <div className="app-shell">
      <TopHeader title={title} onBack={onBack} rightSlot={rightSlot} />
      <div className="app-shell__content">{children}</div>
      {showBottomNav && <BottomNav active={activeTab} onNavigate={onNavigateTab} />}
    </div>
  );
}
