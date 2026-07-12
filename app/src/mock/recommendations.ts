import type { Recommendation } from '../types';

export const recommendations: Recommendation[] = [
  {
    bookId: 'book_001',
    hookLine: '느린 문장 속에서 위로를 찾고 싶은 밤에',
    matchedTrait: '잔잔함',
    explanation: '평소 잔잔한 정서를 선호하시는 회원님의 결과 서정성이 높은 이 책이 잘 맞아요.',
  },
  {
    bookId: 'book_006',
    hookLine: '하루의 소음을 잠시 내려놓고 싶다면',
    matchedTrait: '잔잔함',
    explanation: '담백한 문체와 느린 전개를 선호하는 취향과 결이 가장 가까운 책이에요.',
  },
  {
    bookId: 'book_004',
    hookLine: '오래된 우정이 그리워지는 계절',
    matchedTrait: '여운',
    explanation: '긴 여운을 선호하시는 회원님께 그리움이라는 정서가 짙게 남는 책을 추천해요.',
  },
  {
    bookId: 'book_007',
    hookLine: '고요한 밤, 먼 곳을 향한 그리움',
    matchedTrait: '서정성',
    explanation: '서정적인 풍경 묘사를 즐기시는 취향에 맞춰 골라본 책이에요.',
  },
];
