import { useState } from 'react';
import { useReview } from '../hooks/useReview';
import { useBook } from '../hooks/useBook';
import { useSimilarReviewBooks } from '../hooks/useSimilarReviewBooks';
import { Avatar } from '../components/common/Avatar';
import { Tag } from '../components/common/Tag';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { SimilarBookByReviewCard } from '../components/review/SimilarBookByReviewCard';
import './ReviewDetailPage.css';

interface ReviewDetailPageProps {
  reviewId: string;
  onSelectBook: (bookId: string) => void;
}

export function ReviewDetailPage({ reviewId, onSelectBook }: ReviewDetailPageProps) {
  const { data: review, isLoading } = useReview(reviewId);
  const { data: book } = useBook(review?.bookId ?? '');
  const { data: similarBooks, isLoading: similarLoading } = useSimilarReviewBooks(reviewId);
  const [myReaction, setMyReaction] = useState<'like' | 'dislike' | null>(null);

  if (isLoading || !review) {
    return <div className="review-detail-page empty-state">불러오는 중이에요</div>;
  }

  const likeCount = review.likeCount + (myReaction === 'like' ? 1 : 0);

  return (
    <div className="review-detail-page">
      {book && (
        <Card className="review-detail-page__book" onClick={() => onSelectBook(book.id)}>
          <img className="review-detail-page__book-cover" src={book.coverUrl} alt={book.title} />
          <div>
            <p className="review-detail-page__book-title">{book.title}</p>
            <p className="review-detail-page__book-author">
              {book.author} · {book.publisher}
            </p>
          </div>
        </Card>
      )}

      <div className="review-detail-page__author">
        <Avatar name={review.userName} />
        <div>
          <p className="review-detail-page__name">{review.userName}</p>
          <p className="review-detail-page__date">
            {new Date(review.createdAt).toLocaleDateString('ko-KR')}
          </p>
        </div>
      </div>

      <div className="review-detail-page__emotions">
        {review.emotion.map((e) => (
          <Tag key={e} variant="accent">
            {e}
          </Tag>
        ))}
      </div>

      <p className="review-detail-page__content">{review.content}</p>

      {(review.liked.length > 0 || review.disliked.length > 0) && (
        <Card className="review-detail-page__points">
          {review.liked.length > 0 && (
            <p>
              <strong>좋았던 점</strong> {review.liked.join(', ')}
            </p>
          )}
          {review.disliked.length > 0 && (
            <p>
              <strong>아쉬웠던 점</strong> {review.disliked.join(', ')}
            </p>
          )}
        </Card>
      )}

      <div className="review-detail-page__reactions">
        <Button
          variant="secondary"
          className={myReaction === 'like' ? 'review-detail-page__reaction--active' : ''}
          onClick={() => setMyReaction((prev) => (prev === 'like' ? null : 'like'))}
        >
          좋아요 {likeCount}
        </Button>
        <Button
          variant="secondary"
          className={myReaction === 'dislike' ? 'review-detail-page__reaction--active' : ''}
          onClick={() => setMyReaction((prev) => (prev === 'dislike' ? null : 'dislike'))}
        >
          싫어요
        </Button>
      </div>

      <hr className="review-detail-page__divider" />

      <p className="review-detail-page__section-title">이 리뷰와 결이 비슷한 후기의 책</p>

      {similarLoading && (
        <div className="review-detail-page__skeletons">
          <div className="review-detail-page__skeleton" />
          <div className="review-detail-page__skeleton" />
        </div>
      )}

      {!similarLoading && similarBooks.length === 0 && (
        <p className="empty-state">아직 비슷한 후기를 찾지 못했어요</p>
      )}

      {!similarLoading &&
        similarBooks.map((row) => (
          <SimilarBookByReviewCard
            key={`${row.sourceReviewId}-${row.bookId}`}
            recommendation={row}
            onClick={onSelectBook}
          />
        ))}
    </div>
  );
}
