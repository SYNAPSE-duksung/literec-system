import type { ScreenName } from '../../types';
import { HomeIcon, ListIcon, SearchIcon, UserIcon } from '../../icons';
import './BottomNav.css';

const TABS: { name: Extract<ScreenName, 'home' | 'board' | 'search' | 'mypage'>; label: string; Icon: typeof HomeIcon }[] = [
  { name: 'home', label: '홈', Icon: HomeIcon },
  { name: 'board', label: '게시판', Icon: ListIcon },
  { name: 'search', label: '검색', Icon: SearchIcon },
  { name: 'mypage', label: '마이페이지', Icon: UserIcon },
];

interface BottomNavProps {
  active: ScreenName;
  onNavigate: (name: (typeof TABS)[number]['name']) => void;
}

export function BottomNav({ active, onNavigate }: BottomNavProps) {
  return (
    <nav className="bottom-nav">
      {TABS.map(({ name, label, Icon }) => (
        <button
          key={name}
          type="button"
          className={['bottom-nav__item', active === name ? 'bottom-nav__item--active' : '']
            .filter(Boolean)
            .join(' ')}
          onClick={() => onNavigate(name)}
        >
          <Icon width={20} height={20} />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}
