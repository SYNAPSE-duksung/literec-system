import { useUserProfile } from '../hooks/useUserProfile';
import { useBooks } from '../hooks/useBooks';
import { useReviews } from '../hooks/useReviews';
import { CURRENT_USER_ID } from '../constants/user';
import { Avatar } from '../components/common/Avatar';
import { BookCard } from '../components/book/BookCard';
import { ReviewCard } from '../components/review/ReviewCard';
import './MyPage.css';

interface MyPageProps {
  onSelectBook: (bookId: string) => void;
  onSelectReview: (reviewId: string) => void;
}

export function MyPage({ onSelectBook, onSelectReview }: MyPageProps) {
  const { data: profile } = useUserProfile();
  const { data: books } = useBooks();
  const { data: reviews } = useReviews();

  const likedBooks = books.filter((book) => profile?.likedBookIds.includes(book.id));
  const myReviews = reviews.filter((review) => review.userId === CURRENT_USER_ID);

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

      <p className="mypage__section-title">좋아한 책 {likedBooks.length}개</p>
      {likedBooks.length === 0 && <p className="empty-state">아직 좋아한 책이 없어요</p>}
      {likedBooks.map((book) => (
        <BookCard key={book.id} book={book} onClick={() => onSelectBook(book.id)} />
      ))}

      <p className="mypage__section-title">내가 남긴 기록 {myReviews.length}개</p>
      {myReviews.length === 0 && <p className="empty-state">아직 남긴 기록이 없어요</p>}
      {myReviews.map((review) => (
        <ReviewCard key={review.id} review={review} onClick={() => onSelectReview(review.id)} />
      ))}
    </div>
  );
}
