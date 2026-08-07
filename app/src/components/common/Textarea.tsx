import type { TextareaHTMLAttributes } from 'react';
import './Input.css';

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
}

export function Textarea({ label, className, id, ...rest }: TextareaProps) {
  return (
    <div className="field">
      {label && (
        <label className="field__label" htmlFor={id}>
          {label}
        </label>
      )}
      <textarea
        id={id}
        className={['field__control', className].filter(Boolean).join(' ')}
        {...rest}
      />
    </div>
  );
}
