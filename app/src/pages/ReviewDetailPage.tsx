import { useState } from 'react';
import { useReview } from '../hooks/useReview';
import { useBook } from '../hooks/useBook';
import { useSimilarReviewBooks } from '../hooks/useSimilarReviewBooks';
import { useReviewReaction } from '../hooks/useReviewReaction';
import { useDeleteReview } from '../hooks/useDeleteReview';
import { useUserProfile } from '../hooks/useUserProfile';
import { Avatar } from '../components/common/Avatar';
import { Tag } from '../components/common/Tag';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { SimilarBookByReviewCard } from '../components/review/SimilarBookByReviewCard';
import { HeartIcon, ThumbsDownIcon } from '../icons';
import './ReviewDetailPage.css';

interface ReviewDetailPageProps {
  reviewId: string;
  onSelectBook: (bookId: string) => void;
  onEdit: (bookId: string, reviewId: string) => void;
  onDeleted: () => void;
}

export function ReviewDetailPage({ reviewId, onSelectBook, onEdit, onDeleted }: ReviewDetailPageProps) {
  const { data: review, isLoading } = useReview(reviewId);
  const { data: book } = useBook(review?.bookId ?? '');
  const { data: similarBooks, isLoading: similarLoading } = useSimilarReviewBooks(reviewId);
  const { myReaction, setReaction } = useReviewReaction(reviewId);
  const { data: profile } = useUserProfile();
  const { deleteReview } = useDeleteReview();
  const [isDeleting, setIsDeleting] = useState(false);

  if (isLoading || !review) {
    return <div className="review-detail-page empty-state">불러오는 중이에요</div>;
  }

  const likeCount = review.likeCount + (myReaction === 'like' ? 1 : 0);
  const isOwnReview = review.userId === profile?.userId;

  const handleDelete = async () => {
    if (!window.confirm('이 기록을 삭제할까요? 삭제하면 되돌릴 수 없어요.')) return;
    setIsDeleting(true);
    try {
      await deleteReview(review.id);
      onDeleted();
    } catch {
      setIsDeleting(false);
      window.alert('삭제에 실패했어요. 잠시 후 다시 시도해주세요.');
    }
  };

  return (
    <div className="review-detail-page">
      {book && (
        <Card className="review-detail-page__book" onClick={() => onSelectBook(book.id)}>
          <img
            className="review-detail-page__book-cover"
            src={book.coverUrl}
            alt={book.title}
            decoding="async"
          />
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
        {isOwnReview && (
          <div className="review-detail-page__owner-actions">
            <Button
              variant="text"
              className="review-detail-page__edit-btn"
              onClick={() => onEdit(review.bookId, review.id)}
            >
              수정
            </Button>
            <Button
              variant="text"
              className="review-detail-page__delete-btn"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? '삭제 중…' : '삭제'}
            </Button>
          </div>
        )}
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
          aria-pressed={myReaction === 'like'}
          onClick={() => setReaction(myReaction === 'like' ? null : 'like')}
        >
          <HeartIcon width={16} height={16} filled={myReaction === 'like'} /> 좋아요 {likeCount}
        </Button>
        <Button
          variant="secondary"
          className={myReaction === 'dislike' ? 'review-detail-page__reaction--active' : ''}
          aria-pressed={myReaction === 'dislike'}
          onClick={() => setReaction(myReaction === 'dislike' ? null : 'dislike')}
        >
          <ThumbsDownIcon width={16} height={16} filled={myReaction === 'dislike'} /> 싫어요
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
