import type { HTMLAttributes, KeyboardEvent } from 'react';
import './Card.css';

interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, 'onClick'> {
  onClick?: () => void;
}

export function Card({ className, onClick, onKeyDown, role, tabIndex, ...rest }: CardProps) {
  const classes = ['card', className].filter(Boolean).join(' ');

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    onKeyDown?.(event);
    if (onClick && !event.defaultPrevented && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      onClick();
    }
  };

  return (
    <div
      className={classes}
      onClick={onClick}
      onKeyDown={onClick ? handleKeyDown : onKeyDown}
      role={onClick ? (role ?? 'button') : role}
      tabIndex={onClick ? (tabIndex ?? 0) : tabIndex}
      {...rest}
    />
  );
}
