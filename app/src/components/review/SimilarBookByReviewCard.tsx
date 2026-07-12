import type { SimilarReviewRecommendation } from '../../types';
import { useBook } from '../../hooks/useBook';
import { HeartIcon } from '../../icons';
import { Card } from '../common/Card';
import './SimilarBookByReviewCard.css';

interface SimilarBookByReviewCardProps {
  recommendation: SimilarReviewRecommendation;
  onClick: (bookId: string) => void;
}

export function SimilarBookByReviewCard({ recommendation, onClick }: SimilarBookByReviewCardProps) {
  const { data: book, isLoading } = useBook(recommendation.bookId);

  if (isLoading || !book) {
    return <Card className="similar-book-card similar-book-card--skeleton" />;
  }

  return (
    <Card className="similar-book-card" onClick={() => onClick(book.id)}>
      <img className="similar-book-card__cover" src={book.coverUrl} alt={book.title} />
      <div className="similar-book-card__info">
        <p className="similar-book-card__title">{book.title}</p>
        <p className="similar-book-card__author">
          {book.author} · {book.publisher}
        </p>
        <p className="similar-book-card__snippet">“{recommendation.matchedReviewSnippet}”</p>
        <p className="similar-book-card__reason">
          <HeartIcon width={12} height={12} filled />
          <span>{recommendation.similarityReason}</span>
        </p>
      </div>
    </Card>
  );
}
