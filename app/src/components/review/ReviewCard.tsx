import type { Review } from '../../types';
import { useBook } from '../../hooks/useBook';
import { Avatar } from '../common/Avatar';
import { Tag } from '../common/Tag';
import { Card } from '../common/Card';
import './ReviewCard.css';

interface ReviewCardProps {
  review: Review;
  onClick: () => void;
  showBook?: boolean;
}

export function ReviewCard({ review, onClick, showBook = true }: ReviewCardProps) {
  const { data: book } = useBook(showBook ? review.bookId : '');

  return (
    <Card className="review-card" onClick={onClick}>
      <div className="review-card__header">
        <Avatar name={review.userName} />
        <div className="review-card__meta">
          <p className="review-card__name">{review.userName}</p>
          <p className="review-card__date">{new Date(review.createdAt).toLocaleDateString('ko-KR')}</p>
        </div>
      </div>
      {showBook && book && (
        <p className="review-card__book">
          {book.title} · {book.author}
        </p>
      )}
      <div className="review-card__emotions">
        {review.emotion.map((e) => (
          <Tag key={e} variant="accent">
            {e}
          </Tag>
        ))}
      </div>
      <p className="review-card__content">{review.content}</p>
      <p className="review-card__like">좋아요 {review.likeCount}</p>
    </Card>
  );
}
