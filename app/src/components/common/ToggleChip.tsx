import type { ButtonHTMLAttributes } from 'react';
import './ToggleChip.css';

interface ToggleChipProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onClick'> {
  selected: boolean;
  onToggle: () => void;
}

export function ToggleChip({ selected, onToggle, className, children, ...rest }: ToggleChipProps) {
  const classes = ['toggle-chip', selected ? 'toggle-chip--selected' : '', className]
    .filter(Boolean)
    .join(' ');
  return (
    <button type="button" className={classes} onClick={onToggle} aria-pressed={selected} {...rest}>
      {children}
    </button>
  );
}
