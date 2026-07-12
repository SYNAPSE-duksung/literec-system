import './Avatar.css';

export function Avatar({ name }: { name: string }) {
  const initial = name.trim().charAt(0) || '?';
  return <div className="avatar">{initial}</div>;
}
