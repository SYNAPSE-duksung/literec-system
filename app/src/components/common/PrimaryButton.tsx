import type { ButtonHTMLAttributes } from 'react';
import { Button } from './Button';

export function PrimaryButton(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <Button variant="primary" {...props} />;
}
