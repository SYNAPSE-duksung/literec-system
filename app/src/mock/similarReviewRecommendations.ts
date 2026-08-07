import type { SimilarReviewRecommendation } from '../types';

// 하드룰: bookId는 sourceReviewId가 가리키는 리뷰의 bookId와 항상 달라야 한다.
// review_001 -> book_001 / review_003 -> book_002 / review_005 -> book_003 (mock/reviews.ts 참고)
export const similarReviewRecommendations: SimilarReviewRecommendation[] = [
  {
    sourceReviewId: 'review_001',
    bookId: 'book_004',
    matchedReviewSnippet: '십 년이라는 시간의 거리가 실감 나게 그려져서 좋았다.',
    similarityReason: '느린 호흡과 그리움의 정서가 닮아 있어요',
  },
  {
    sourceReviewId: 'review_001',
    bookId: 'book_006',
    matchedReviewSnippet: '식탁 위 음식 하나하나에 담긴 기억을 읽는 것만으로도 마음이 따뜻해졌다.',
    similarityReason: '담담한 문체를 좋아하는 독자들이 함께 남긴 후기예요',
  },
  {
    sourceReviewId: 'review_003',
    bookId: 'book_006',
    matchedReviewSnippet: '식탁 위 음식 하나하나에 담긴 기억을 읽는 것만으로도 마음이 따뜻해졌다.',
    similarityReason: '위로와 담백함을 함께 느낀 독자들의 후기예요',
  },
  {
    sourceReviewId: 'review_005',
    bookId: 'book_001',
    matchedReviewSnippet: '섬 풍경 묘사가 정말 좋았다. 계절이 바뀌는 걸 문장으로 느낄 수 있는 책.',
    similarityReason: '섬세한 묘사에 마음이 움직인 독자들의 후기예요',
  },
  {
    sourceReviewId: 'review_005',
    bookId: 'book_008',
    matchedReviewSnippet: '관찰자의 담담한 기록이 마음에 오래 남았다.',
    similarityReason: '섬세한 관찰과 기록이라는 결이 비슷해요',
  },
];
