import type { ReactNode } from 'react';
import { BackIcon } from '../../icons';
import './TopHeader.css';

interface TopHeaderProps {
  title: string;
  onBack?: () => void;
  rightSlot?: ReactNode;
}

export function TopHeader({ title, onBack, rightSlot }: TopHeaderProps) {
  return (
    <header className="top-header">
      <div className="top-header__left">
        {onBack && (
          <button type="button" className="top-header__back" onClick={onBack} aria-label="뒤로가기">
            <BackIcon width={20} height={20} />
          </button>
        )}
        <span className="top-header__title">{title}</span>
      </div>
      {rightSlot && <div className="top-header__right">{rightSlot}</div>}
    </header>
  );
}
