import type { MyListType } from '../types';
import { useUserProfile } from '../hooks/useUserProfile';
import { useBooks } from '../hooks/useBooks';
import { useReviews } from '../hooks/useReviews';
import { Avatar } from '../components/common/Avatar';
import { Button } from '../components/common/Button';
import { BookCard } from '../components/book/BookCard';
import { ReviewCard } from '../components/review/ReviewCard';
import './MyPage.css';

const PREVIEW_LIMIT = 3;

interface MyPageProps {
  onSelectBook: (bookId: string) => void;
  onSelectReview: (reviewId: string) => void;
  onViewAll: (listType: MyListType) => void;
}

export function MyPage({ onSelectBook, onSelectReview, onViewAll }: MyPageProps) {
  const { data: profile, dislikedBookIds } = useUserProfile();
  const { data: books } = useBooks();
  const { data: reviews } = useReviews();

  const likedBooks = books.filter((book) => profile?.likedBookIds.includes(book.id));
  const dislikedBooks = books.filter((book) => dislikedBookIds.includes(book.id));
  const myReviews = reviews.filter((review) => review.userId === profile?.userId);

  return (
    <div className="mypage">
      <div className="mypage__profile">
        <Avatar name="나" />
        <div>
          <p className="mypage__name">나</p>
          <p className="mypage__preferences">
            {profile && profile.preferredEmotions.length > 0
              ? profile.preferredEmotions.join(', ')
              : '선호 정서를 아직 설정하지 않았어요'}
          </p>
        </div>
      </div>

      <div className="mypage__section-header">
        <p className="mypage__section-title">좋아한 책 {likedBooks.length}개</p>
        {likedBooks.length > PREVIEW_LIMIT && (
          <Button variant="text" onClick={() => onViewAll('likedBooks')}>
            전체 보기
          </Button>
        )}
      </div>
      {likedBooks.length === 0 && <p className="empty-state">아직 좋아한 책이 없어요</p>}
      {likedBooks.slice(0, PREVIEW_LIMIT).map((book) => (
        <BookCard key={book.id} book={book} onClick={() => onSelectBook(book.id)} />
      ))}

      <div className="mypage__section-header">
        <p className="mypage__section-title">싫어요 표시한 책 {dislikedBooks.length}개</p>
        {dislikedBooks.length > PREVIEW_LIMIT && (
          <Button variant="text" onClick={() => onViewAll('dislikedBooks')}>
            전체 보기
          </Button>
        )}
      </div>
      {dislikedBooks.length === 0 && <p className="empty-state">아직 싫어요 표시한 책이 없어요</p>}
      {dislikedBooks.slice(0, PREVIEW_LIMIT).map((book) => (
        <BookCard key={book.id} book={book} onClick={() => onSelectBook(book.id)} />
      ))}

      <div className="mypage__section-header">
        <p className="mypage__section-title">내가 남긴 기록 {myReviews.length}개</p>
        {myReviews.length > PREVIEW_LIMIT && (
          <Button variant="text" onClick={() => onViewAll('myReviews')}>
            전체 보기
          </Button>
        )}
      </div>
      {myReviews.length === 0 && <p className="empty-state">아직 남긴 기록이 없어요</p>}
      {myReviews.slice(0, PREVIEW_LIMIT).map((review) => (
        <ReviewCard key={review.id} review={review} onClick={() => onSelectReview(review.id)} />
      ))}
    </div>
  );
}
