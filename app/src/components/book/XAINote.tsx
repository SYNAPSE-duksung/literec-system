import { HeartIcon } from '../../icons';
import './XAINote.css';

export function XAINote({ text }: { text: string }) {
  return (
    <p className="xai-note">
      <HeartIcon width={14} height={14} filled />
      <span>{text}</span>
    </p>
  );
}
