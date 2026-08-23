import type { HTMLAttributes } from 'react';
import './Tag.css';

interface TagProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'accent';
}

export function Tag({ variant = 'default', className, ...rest }: TagProps) {
  const classes = ['tag', `tag--${variant}`, className].filter(Boolean).join(' ');
  return <span className={classes} {...rest} />;
}
