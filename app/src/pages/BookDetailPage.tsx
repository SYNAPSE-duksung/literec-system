import { useEffect, useState } from 'react';
import { useBook } from '../hooks/useBook';
import { useReviewsByBook } from '../hooks/useReviewsByBook';
import { useUserProfile } from '../hooks/useUserProfile';
import { IdentityRadarChart } from '../components/book/IdentityRadarChart';
import { XAINote } from '../components/book/XAINote';
import { ReviewCard } from '../components/review/ReviewCard';
import { Card } from '../components/common/Card';
import { Tag } from '../components/common/Tag';
import { Button } from '../components/common/Button';
import { HeartIcon, ThumbsDownIcon } from '../icons';
import './BookDetailPage.css';

interface BookDetailPageProps {
  bookId: string;
  onSelectReview: (reviewId: string) => void;
  onWriteReview: (bookId: string) => void;
}

const SYNOPSIS_PREVIEW_LIMIT = 150;

export function BookDetailPage({ bookId, onSelectReview, onWriteReview }: BookDetailPageProps) {
  const { data: book, isLoading } = useBook(bookId);
  const { data: reviews, isLoading: reviewsLoading } = useReviewsByBook(bookId);
  const { data: profile, dislikedBookIds, setBookReaction } = useUserProfile();
  const [synopsisExpanded, setSynopsisExpanded] = useState(false);

  useEffect(() => {
    setSynopsisExpanded(false);
  }, [bookId]);

  if (isLoading || !book) {
    return <div className="book-detail-page empty-state">불러오는 중이에요</div>;
  }

  const liked = profile?.likedBookIds.includes(book.id) ?? false;
  const disliked = dislikedBookIds.includes(book.id);
  const synopsisTruncatable = book.synopsis.length > SYNOPSIS_PREVIEW_LIMIT;
  const displayedSynopsis =
    synopsisTruncatable && !synopsisExpanded
      ? `${book.synopsis.slice(0, SYNOPSIS_PREVIEW_LIMIT)}…`
      : book.synopsis;

  return (
    <div className="book-detail-page">
      <div className="book-detail-page__summary">
        <img className="book-detail-page__cover" src={book.coverUrl} alt={book.title} />
        <div>
          <p className="book-detail-page__title">{book.title}</p>
          <p className="book-detail-page__author">
            {book.author} · {book.publisher}
          </p>
          <div className="book-detail-page__tags">
            {book.identityVectors
              .slice()
              .sort((a, b) => b.score - a.score)
              .slice(0, 2)
              .map((v) => (
                <Tag key={v.trait} variant="accent">
                  {v.trait}
                </Tag>
              ))}
          </div>
        </div>
      </div>

      <div className="book-detail-page__reactions">
        <Button
          variant="secondary"
          className={liked ? 'book-detail-page__reaction--active' : ''}
          aria-pressed={liked}
          onClick={() => setBookReaction(book.id, liked ? null : 'like')}
        >
          <HeartIcon width={16} height={16} filled={liked} /> 좋아요
        </Button>
        <Button
          variant="secondary"
          className={disliked ? 'book-detail-page__reaction--active' : ''}
          aria-pressed={disliked}
          onClick={() => setBookReaction(book.id, disliked ? null : 'dislike')}
        >
          <ThumbsDownIcon width={16} height={16} filled={disliked} /> 싫어요
        </Button>
      </div>

      <p className="book-detail-page__synopsis">
        {displayedSynopsis}
        {synopsisTruncatable && (
          <button
            type="button"
            className="book-detail-page__synopsis-toggle"
            onClick={() => setSynopsisExpanded((prev) => !prev)}
          >
            {synopsisExpanded ? ' 접기' : ' 더보기'}
          </button>
        )}
      </p>

      <Card className="book-detail-page__radar-card">
        <p className="book-detail-page__section-title">이 책의 결</p>
        <IdentityRadarChart vectors={book.identityVectors} />
        <XAINote text={`${book.identityVectors[0]?.trait ?? ''} 성향이 두드러지는 책이에요`} />
      </Card>

      <div className="book-detail-page__reviews-header">
        <p className="book-detail-page__section-title">독자들의 기록 {reviews.length}개</p>
        <Button variant="secondary" className="book-detail-page__write-btn" onClick={() => onWriteReview(book.id)}>
          기록 남기기
        </Button>
      </div>

      {!reviewsLoading && reviews.length === 0 && <p className="empty-state">아직 기록이 없어요</p>}

      {reviews.map((review) => (
        <ReviewCard
          key={review.id}
          review={review}
          onClick={() => onSelectReview(review.id)}
          showBook={false}
        />
      ))}
    </div>
  );
}
