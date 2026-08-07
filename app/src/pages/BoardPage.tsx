import { useState } from 'react';
import { useReviews } from '../hooks/useReviews';
import { ReviewCard } from '../components/review/ReviewCard';
import { Input } from '../components/common/Input';
import { Button } from '../components/common/Button';
import './BoardPage.css';

interface BoardPageProps {
  onSelectReview: (reviewId: string) => void;
  onWriteReview: () => void;
}

export function BoardPage({ onSelectReview, onWriteReview }: BoardPageProps) {
  const [query, setQuery] = useState('');
  const { data: reviews, isLoading } = useReviews(query);

  return (
    <div className="board-page">
      <div className="board-page__header">
        <h2 className="board-page__title">독서 기록</h2>
        <Button variant="secondary" className="board-page__write-btn" onClick={onWriteReview}>
          기록하기
        </Button>
      </div>

      <Input
        id="board-search"
        placeholder="내용 또는 정서로 검색해보세요"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      <div className="board-page__list">
        {!isLoading && reviews.length === 0 && <p className="empty-state">아직 기록이 없어요</p>}
        {reviews.map((review) => (
          <ReviewCard key={review.id} review={review} onClick={() => onSelectReview(review.id)} />
        ))}
      </div>
    </div>
  );
}
