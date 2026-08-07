import type { Book } from '../types';

export const books: Book[] = [
  {
    id: 'book_001',
    title: '섬의 아이',
    author: '한소연',
    publisher: '해안출판사',
    coverUrl: 'https://placehold.co/200x300/EFEAE0/1A1A1A?text=섬의+아이',
    synopsis:
      '외딴 섬에서 나고 자란 소녀가 육지로 나가기까지의 열여덟 해를 담담하게 그린 성장 소설. 잔잔한 문장 아래 상실과 그리움이 흐른다.',
    identityVectors: [
      { trait: '잔잔함', score: 88, keywords: ['담담한 문체', '느린 호흡'] },
      { trait: '몰입감', score: 62, keywords: ['잔잔한 전개'] },
      { trait: '서정성', score: 92, keywords: ['섬 풍경', '계절감'] },
      { trait: '현실성', score: 70, keywords: ['성장통'] },
      { trait: '여운', score: 85, keywords: ['긴 여운'] },
    ],
  },
  {
    id: 'book_002',
    title: '밤의 해변에서',
    author: '정우진',
    publisher: '야간출판사',
    coverUrl: 'https://placehold.co/200x300/EFEAE0/1A1A1A?text=밤의+해변에서',
    synopsis:
      '이혼 후 낯선 도시로 떠난 남자가 우연히 만난 사람들과 나누는 대화를 통해 스스로를 위로해가는 이야기.',
    identityVectors: [
      { trait: '잔잔함', score: 75, keywords: ['위로'] },
      { trait: '몰입감', score: 68, keywords: ['대화 중심'] },
      { trait: '서정성', score: 80, keywords: ['밤바다'] },
      { trait: '현실성', score: 82, keywords: ['이혼', '중년'] },
      { trait: '여운', score: 78, keywords: ['담백한 위로'] },
    ],
  },
  {
    id: 'book_003',
    title: '유리의 계절',
    author: '이서현',
    publisher: '투명출판사',
    coverUrl: 'https://placehold.co/200x300/EFEAE0/1A1A1A?text=유리의+계절',
    synopsis:
      '유리 공예가인 주인공이 스승의 죽음 이후 자신만의 작품 세계를 찾아가는 과정을 그린 예술가 소설.',
    identityVectors: [
      { trait: '잔잔함', score: 55, keywords: ['긴장과 몰입'] },
      { trait: '몰입감', score: 90, keywords: ['빠른 전개'] },
      { trait: '서정성', score: 65, keywords: ['공예 묘사'] },
      { trait: '현실성', score: 60, keywords: ['장인정신'] },
      { trait: '여운', score: 70, keywords: ['성취와 상실'] },
    ],
  },
  {
    id: 'book_004',
    title: '두 번째 여름',
    author: '박지민',
    publisher: '여름출판사',
    coverUrl: 'https://placehold.co/200x300/EFEAE0/1A1A1A?text=두+번째+여름',
    synopsis:
      '십 년 만에 재회한 두 친구가 함께한 마지막 여름을 회상하며 서로에게 하지 못했던 말을 꺼내놓는다.',
    identityVectors: [
      { trait: '잔잔함', score: 70, keywords: ['잔잔한 재회'] },
      { trait: '몰입감', score: 74, keywords: ['우정'] },
      { trait: '서정성', score: 76, keywords: ['여름 풍경'] },
      { trait: '현실성', score: 68, keywords: ['우정과 거리감'] },
      { trait: '여운', score: 88, keywords: ['긴 여운', '그리움'] },
    ],
  },
  {
    id: 'book_005',
    title: '기록되지 않은 밤',
    author: '최다은',
    publisher: '연대출판사',
    coverUrl: 'https://placehold.co/200x300/EFEAE0/1A1A1A?text=기록되지+않은+밤',
    synopsis:
      '재난 이후의 도시를 배경으로, 살아남은 이들이 서로의 이야기를 기록하며 연대하는 근미래 소설.',
    identityVectors: [
      { trait: '잔잔함', score: 40, keywords: ['긴장감'] },
      { trait: '몰입감', score: 95, keywords: ['긴박한 전개'] },
      { trait: '서정성', score: 55, keywords: ['폐허의 미학'] },
      { trait: '현실성', score: 50, keywords: ['근미래 설정'] },
      { trait: '여운', score: 72, keywords: ['연대'] },
    ],
  },
  {
    id: 'book_006',
    title: '조용한 식탁',
    author: '한소연',
    publisher: '식탁출판사',
    coverUrl: 'https://placehold.co/200x300/EFEAE0/1A1A1A?text=조용한+식탁',
    synopsis:
      '홀로 사는 노년의 요리사가 매일의 식사를 준비하며 지나온 삶을 돌아보는 잔잔한 에세이풍 소설.',
    identityVectors: [
      { trait: '잔잔함', score: 95, keywords: ['정적인 하루'] },
      { trait: '몰입감', score: 50, keywords: ['느린 전개'] },
      { trait: '서정성', score: 85, keywords: ['음식과 기억'] },
      { trait: '현실성', score: 78, keywords: ['노년의 삶'] },
      { trait: '여운', score: 90, keywords: ['담백한 여운'] },
    ],
  },
  {
    id: 'book_007',
    title: '먼 곳의 신호',
    author: '오세훈',
    publisher: '신호출판사',
    coverUrl: 'https://placehold.co/200x300/EFEAE0/1A1A1A?text=먼+곳의+신호',
    synopsis:
      '천문대에서 일하는 관측자가 매일 밤 먼 별의 신호를 기다리며 떠나온 고향을 그리워하는 이야기.',
    identityVectors: [
      { trait: '잔잔함', score: 80, keywords: ['고요한 밤'] },
      { trait: '몰입감', score: 65, keywords: ['잔잔한 몰입'] },
      { trait: '서정성', score: 88, keywords: ['밤하늘'] },
      { trait: '현실성', score: 55, keywords: ['관측자의 일상'] },
      { trait: '여운', score: 82, keywords: ['그리움'] },
    ],
  },
  {
    id: 'book_008',
    title: '얼음의 이름',
    author: '윤가을',
    publisher: '빙하출판사',
    coverUrl: 'https://placehold.co/200x300/EFEAE0/1A1A1A?text=얼음의+이름',
    synopsis:
      '빙하학자가 사라져가는 빙하에 이름을 붙이며 기록을 남기는, 상실과 기록에 관한 짧은 소설.',
    identityVectors: [
      { trait: '잔잔함', score: 72, keywords: ['담담한 기록'] },
      { trait: '몰입감', score: 58, keywords: ['관찰자 시점'] },
      { trait: '서정성', score: 79, keywords: ['빙하 풍경'] },
      { trait: '현실성', score: 66, keywords: ['기후 위기'] },
      { trait: '여운', score: 84, keywords: ['상실'] },
    ],
  },
];
