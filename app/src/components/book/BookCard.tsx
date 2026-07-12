import type { ReactNode } from 'react';
import type { Book } from '../../types';
import { useUserProfile } from '../../hooks/useUserProfile';
import { HeartIcon } from '../../icons';
import { Card } from '../common/Card';
import { Tag } from '../common/Tag';
import './BookCard.css';

interface BookCardProps {
  book: Book;
  onClick: () => void;
  children?: ReactNode;
  showLikeButton?: boolean;
}

export function BookCard({ book, onClick, children, showLikeButton = true }: BookCardProps) {
  const { data: profile, toggleLikedBook } = useUserProfile();
  const liked = profile?.likedBookIds.includes(book.id) ?? false;
  const topTrait = [...book.identityVectors].sort((a, b) => b.score - a.score)[0];

  return (
    <Card className="book-card" onClick={onClick}>
      {showLikeButton && (
        <button
          type="button"
          className={['book-card__like', liked ? 'book-card__like--active' : ''].filter(Boolean).join(' ')}
          aria-label={liked ? '좋아요 취소' : '좋아요'}
          aria-pressed={liked}
          onClick={(e) => {
            e.stopPropagation();
            toggleLikedBook(book.id);
          }}
        >
          <HeartIcon width={18} height={18} filled={liked} />
        </button>
      )}
      <div className="book-card__row">
        <img className="book-card__cover" src={book.coverUrl} alt={book.title} />
        <div className="book-card__info">
          <p className="book-card__title">{book.title}</p>
          <p className="book-card__author">
            {book.author} · {book.publisher}
          </p>
          {topTrait && <Tag variant="accent">{topTrait.trait}</Tag>}
        </div>
      </div>
      {children}
    </Card>
  );
}
