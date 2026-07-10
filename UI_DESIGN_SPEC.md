# UI 명세서 초안

## UI 설계도 — Day 12 완성 (Claude Code 투입용)

이 문서는 일정표가 아니라 **설계 명세서**입니다. 화면 구조, 컴포넌트 트리, 데이터 흐름, 상태 설계를 코드 작성 전에 확정합니다.

Claude Code에 이 문서를 통째로 제공하고 "섹션 X 기준으로 Y 화면/컴포넌트를 구현해줘"라고 요청하면 됩니다.

목표: **Day 12까지 아래 명세 전부를 실제 동작하는 mock 기반 UI로 완성.**

---

## 1. 기술 스택 (최소 구성)

프로토타입 목적에 맞게 의존성을 최소화한다. React 자체 외에는 사실상 추가 라이브러리가 없다.

| 영역 | 선택 | 비고 |
|---|---|---|
| 빌드/런타임 | React + Vite (JS, TS 선택사항) | Next.js 대신 — 라우팅/SSR 불필요 |
| 화면 전환 | 컴포넌트 내부 state (`screen` state machine) | 별도 라우팅 라이브러리 없음 |
| 스타일링 | plain CSS (CSS 변수로 디자인 토큰 관리) 또는 inline style 객체 | Tailwind 제거 |
| 서버 상태 | `useState` + `useEffect` 기반 커스텀 훅 | React Query 제거 — 지금은 서버가 없어 캐싱이 의미 없음 |
| 전역 상태 | 최상위 `App` 컴포넌트 state (필요 시 Context 1개) | Zustand 제거 |
| 리뷰 작성 입력 | `<textarea>` | Tiptap 제거 |
| 아이덴티티 레이더 차트 | 직접 그린 SVG polygon (좌표 계산 함수 1개) | Recharts 제거 |
| 아이콘 | lucide-react (선택) 또는 inline SVG | 유지해도 되는 유일한 의존성 — 부담되면 inline SVG로 대체 가능 |

**제거로 얻는 것**: `npm install` 목록이 사실상 `react`, `react-dom`, `vite` 3개(+선택적으로 `lucide-react`)로 줄어듦.

---

## 2. 시스템 개요

```
사용자
  │
  ▼
[App.jsx] ── screen state로 현재 화면 관리 (예: { name: "bookDetail", bookId })
  │
  ├─ /components   재사용 UI 요소 (화면 컴포넌트 포함)
  ├─ /hooks        데이터 접근 계층 (지금은 mock 배열 반환, 추후 fetch 호출로 내부만 교체)
  ├─ /mock         정적 JS/JSON 배열 (스키마는 실제 API 응답과 동일하게 유지)
  └─ /styles       CSS 변수(디자인 토큰) + plain CSS 파일
```

### 설계 원칙

1. 컴포넌트는 데이터를 직접 만들지 않는다 — 항상 `/hooks`를 통해서만 데이터를 받는다.
2. 화면 컴포넌트는 레이아웃과 조합만 담당하고, 로직은 훅과 하위 컴포넌트에 위임한다.
3. 모든 훅은 지금 mock을 반환하지만, **반환 타입은 실제 API 응답 타입과 100% 동일**해야 한다. (다음 단계부터 훅 내부 구현만 교체 → 컴포넌트 코드는 무수정)
4. URL 라우팅이 없으므로 "화면"은 `/board/[reviewId]` 같은 경로 표기가 아니라 **화면 이름 + 파라미터**로 표현한다 (섹션 6 참고).

---

## 3. 화면 흐름도 (Screen Flow)

```
[로그인] ──(회원가입 클릭)──> [회원가입] ──(가입 완료)──┐
  │(로그인 완료, 최초 1회)                              │
  ▼                                                     ▼
[온보딩: 정서 선택] ──> [온보딩: 부담요소 선택] ──(완료)──> [홈]
                                                          │
        ┌─────────────────┬──────────────────┬───────────┴───────────┐
        ▼                 ▼                  ▼                       ▼
     [홈 탭]           [게시판 탭]         [검색 탭]              [마이페이지 탭]
        │                 │                  │                       │
        │                 ├─(작성 클릭)──> [리뷰 작성] ──(제출)──> [게시판]
        │                 │                  │
        └──(책 카드)──> [책 상세] <──(책 카드)──────────────────────┘
                            │
                            ├─(리뷰 카드)──> [리뷰 상세] ─┐
                            │                             │
                            └─(기록 남기기)──> [리뷰 작성] │
                                                            │
                            [리뷰 상세] ──(추천 책 카드 클릭)──┘
                               │                    ↑
                               └────────────────────┘
                     유사 리뷰 기반 책 추천 →
                     클릭 시 해당 책 상세로 순환 이동
```

**하단 탭바 4개**: 홈 / 게시판 / 검색 / 마이페이지 — 어느 탭에서든 상시 노출 (상세/작성 화면 진입 시엔 숨김, 뒤로가기로 복귀)

### UI 디자인 예시 (참고)

> 원본 PDF에 모바일형/데스크탑형 와이어프레임 스크린샷이 포함되어 있습니다. 화면별 레이아웃 텍스트 명세는 섹션 6에 상세히 기술되어 있으니, 스크린샷이 필요하면 원본 PDF(`UI_명세서_초안.pdf`)를 함께 참고하세요.

---

## 4. 전역 상태 설계

| 상태 | 범위 | 저장 위치 |
|---|---|---|
| 인증 여부 (`authed`) | 앱 전역 | `App` 최상위 state |
| 현재 로그인 유저 프로필 | 앱 전역 | 커스텀 훅 `useUserProfile` (useState+useEffect) |
| 온보딩 완료 여부 | 앱 전역 | `App` 최상위 state |
| 하단 탭 활성 상태 | 레이아웃 | URL(라우트) 기준, 별도 상태 불필요 |
| 리뷰 작성 폼 입력값 | 화면 로컬 | `useState` (화면 벗어나면 소멸) |

전역 상태를 최소화하고 대부분 서버 상태(커스텀 훅)로 처리한다 — 화면 간 데이터 불일치를 방지하기 위함.

---

## 5. 데이터 스키마 및 훅 명세

### 5.1 타입 정의

```typescript
interface Book {
  id: string;
  title: string;
  author: string;
  coverUrl: string;
  synopsis: string;
  identityVectors: { trait: string; score: number; keywords: string[] }[];
}

interface Review {
  id: string;
  bookId: string;
  userId: string;
  userName: string;
  content: string;
  liked: string[];
  disliked: string[];
  emotion: string[];
  likeCount: number;
  createdAt: string;
}

interface Recommendation {
  bookId: string;
  hookLine: string;
  matchedTrait: string;
  explanation: string;
}

interface UserProfile {
  userId: string;
  preferredEmotions: string[];
  avoidedTraits: string[];
  likedBookIds: string[];
}

// 신규: 리뷰 상세 화면의 "유사 리뷰 기반 책 추천"
interface SimilarReviewRecommendation {
  sourceReviewId: string;
  bookId: string;
  matchedReviewSnippet: string; // 유사 판정된 다른 리뷰의 한 줄 요약
  similarityReason: string;     // 유사 이유 한 줄 설명
}
```

### 5.2 훅 명세

전부 `/hooks`에 위치, useState+useEffect 기반 — 캐싱/재요청 없이 mock 배열을 그대로 반환.

| 훅 | 입력 | 반환 | 사용 화면 |
|---|---|---|---|
| `useBooks()` | - | `Book[]` | 검색, 홈 |
| `useBook(bookId)` | bookId | `Book` | 책 상세 |
| `useRecommendations()` | - | `Recommendation[]` | 홈 |
| `useReviews(filter?)` | 검색어(optional) | `Review[]` | 게시판 |
| `useReviewsByBook(bookId)` | bookId | `Review[]` | 책 상세 |
| `useReview(reviewId)` | reviewId | `Review` | 리뷰 상세 |
| `useUserProfile()` | - | `UserProfile` | 마이페이지, 온보딩 |
| `useSimilarReviewBooks(reviewId)` | reviewId | `SimilarReviewRecommendation[]` | 리뷰 상세 (신규) |

각 훅은 로딩/에러 상태를 함께 반환한다: `{ data, isLoading, isError }`

---

## 6. 화면별 상세 설계 (와이어프레임 레벨)

디자인 토큰(색상/spacing/radius)은 이전 확정안을 그대로 따름: `primary #1A1A1A`, `background #FAFAF8`, `accent #3D5A80`, `border #E5E5E0`, spacing 8/16/24/32/48, radius 카드 12px·버튼 8px, 폰트 Pretendard, 모바일 우선 max-width 390px.

> URL 라우팅이 없으므로 화면 전환은 `App`의 `screen` state로 표현한다. 예: `setScreen({ name: "bookDetail", bookId: "book_001" })`. 아래 각 화면 제목의 괄호는 URL이 아니라 이 `screen.name` 값이다.

### 6.1 로그인 (`screen.name: "login"`)

```
[상단 패딩 64px]
결                          ← 20px 세미볼드
깊이 있는 후기로 책을 만나요   ← 13px, text-secondary
[gap 32px]
이메일 라벨 + input
비밀번호 라벨 + input (type=password)
[gap 24px]
[로그인 버튼] (disabled until 둘 다 4자 이상)
[gap 16px]
계정이 없으신가요? 회원가입 (텍스트 링크) → setScreen({ name: "signup" })
```

상태: `email`, `password` (local) → `canSubmit = email.length>3 && password.length>3`

### 6.2 회원가입 (`screen.name: "signup"`)

```
[뒤로가기 아이콘] → setScreen({ name: "login" })
회원가입 / 몇 가지 정보만 알려주세요
이름 input
이메일 input (형식 검증: /\S+@\S+\.\S+/, 실패 시 인라인 에러 문구)
비밀번호 input
비밀번호 확인 input (불일치 시 인라인 에러 문구)
[가입하고 시작하기 버튼] (전 필드 유효해야 활성화)
이미 계정이 있으신가요? 로그인 (텍스트 링크)
```

### 6.3 온보딩 (`screen.name: "onboarding"`, 2 step)

```
프로그레스 바 (2칸, 현재 step 채움)

Step 1: 어떤 정서를 좋아하세요?
  ToggleChip × 7 (잔잔함/위로/그리움/먹먹함/담백함/설렘/긴장감)
  다음 버튼 (1개 이상 선택 시 활성화)

Step 2: 부담스러운 요소가 있나요?
  ToggleChip × 5 (신파/직접적 감정 자극/느린 전개/잔인한 묘사/장황한 문체)
  완료하고 추천 받기 버튼 (선택 없어도 활성화)
```

완료 시 `useUserProfile` 갱신 → `setScreen({ name: "home" })`

### 6.4 홈 (`screen.name: "home"`, 하단 탭 "홈")

```
TopHeader (제목 "결" + 검색 아이콘)

오늘의 추천              ← 13px text-secondary
회원님의 결과 닮은
책들을 모아봤어요        ← 19px 세미볼드, 2줄

[BookCard + XAINote] × N (useRecommendations)
  카드 클릭 → setScreen({ name: "bookDetail", bookId })

BottomNav (홈 활성)
```

### 6.5 책 상세 (`screen.name: "bookDetail", bookId`)

```
TopHeader (뒤로가기 + 책 제목)

표지(88×144) + 제목/작가/정서태그
줄거리 본문

[이 책의 결] 카드
  RadarChart(identityVectors) — SVG polygon 직접 계산, trait 5개 축

XAI 설명 문구 (하트 아이콘 + explanation)

독자들의 기록 N개              기록 남기기 → setScreen({ name: "reviewWrite", bookId })
[ReviewCard] × N (useReviewsByBook)
  카드 클릭 → setScreen({ name: "reviewDetail", reviewId })
  없으면: "아직 기록이 없어요" 빈 상태
```

### 6.6 게시판 목록 (`screen.name: "board"`, 하단 탭 "게시판")

```
TopHeader
독서 기록                    기록하기 버튼 → setScreen({ name: "reviewWrite", bookId })
검색 input (내용/정서 필터, useReviews(query))
[ReviewCard] × N
  카드 클릭 → setScreen({ name: "reviewDetail", reviewId })
BottomNav (게시판 활성)
```

### 6.7 리뷰 작성 (`screen.name: "reviewWrite", bookId`)

```
TopHeader (뒤로가기 + "기록 남기기")
대상 도서 요약 카드 (표지+제목+작가)
느낀 정서 — ToggleChip 다중 선택
좋았던 점 — input
아쉬웠던 점 — input
기록 — textarea (7행)
[기록 올리기 버튼] (content 비어있지 않아야 활성화)
제출 시 → setScreen({ name: "reviewDetail", reviewId: 새로_생성된_id }) 또는 { name: "board" }
```

### 6.8 리뷰 상세 (`screen.name: "reviewDetail", reviewId`) — ★ 이번 설계의 핵심

```
TopHeader (뒤로가기 + 책 제목)

작성자 아바타 + 이름 + 작성일
정서 태그 (accent 스타일)
본문 (whitespace-pre-wrap)

[좋았던 점 / 아쉬웠던 점] 카드

[좋아요 / 싫어요] 토글 버튼
  - 좋아요: liked===true → 검정 채움, likeCount +1/-1 토글
  - 싫어요: liked===false → 검정 채움 (좋아요와 상호 배타)

──────────────── (구분선, my-6) ────────────────

[신규 섹션] 이 리뷰와 결이 비슷한 후기의 책
  데이터: useSimilarReviewBooks(reviewId)

  섹션 상태:
    - isLoading: 스켈레톤 카드 2개
    - data.length === 0: "아직 비슷한 후기를 찾지 못했어요" (text-secondary, py-6, 중앙정렬)
    - data.length > 0: SimilarBookByReviewCard 세로 나열

  SimilarBookByReviewCard 레이아웃:
  ┌───────────────────────────────────┐
  │ [표지 56×80]  책 제목 (14px 세미볼드) │
  │               작가 (12px text-secondary)│
  │               "유사 리뷰 인용문"       │ ← 12px, 이탤릭 느낌 없이 회색, 큰따옴표로 감싸기
  │               ♡ 유사 이유 한 줄       │ ← 11px accent 색, 하트 아이콘 (XAINote와 동일 패턴)
  └───────────────────────────────────┘

  카드 전체 클릭 → setScreen({ name: "bookDetail", bookId })
```

**중요 규칙:**
- `sourceReviewId === reviewId`인 목록만 필터링해서 보여준다
- 본인이 쓴 리뷰(`userId === 현재 로그인 유저`)여도 동일한 로직으로 동작해야 한다 — 작성자 여부로 섹션을 숨기거나 다르게 그리지 않는다
- 추천된 `bookId`가 원본 리뷰의 `bookId`와 같으면 안 된다 (mock 데이터 작성 시에도 이 규칙 준수)

### 6.9 검색 (`screen.name: "search"`, 하단 탭 "검색")

```
input (autofocus, 제목/작가 실시간 필터)
[BookCard] × N (useBooks() 클라이언트 필터링)
쿼리 있는데 결과 없음 → 빈 상태 문구
BottomNav (검색 활성)
```

### 6.10 마이페이지 (`screen.name: "mypage"`, 하단 탭 "마이페이지")

```
아바타 + 이름 + 선호 정서 요약 (useUserProfile)
좋아한 책 N개 — [BookCard] × N (likedBookIds 기준 필터)
내가 남긴 기록 N개 — [ReviewCard] × N (userId 기준 필터)
BottomNav (마이페이지 활성)
```

### 6.11 관리자 대시보드 (`screen.name: "admin"`, 내부용, 데스크탑 허용)

```
카드형 지표 3~4개 (더미 수치): 오늘 신규 리뷰 수, 파이프라인 상태, 활성 사용자 수
더미 차트 1개 (SVG로 직접 그린 막대그래프, 정적 데이터)
```

---

## 7. 컴포넌트 트리

```
App
├─ Shell (max-w-390 wrapper)
│   ├─ TopHeader
│   ├─ (화면별 page 컴포넌트)
│   └─ BottomNav
│
├─ common/
│   ├─ Button, PrimaryButton
│   ├─ Card
│   ├─ Input, Textarea
│   ├─ Tag
│   ├─ ToggleChip
│   └─ Avatar
│
├─ book/
│   ├─ BookCard              (홈, 검색, 마이페이지 공용)
│   ├─ IdentityRadarChart
│   └─ XAINote
│
└─ review/
    ├─ ReviewCard             (게시판, 책상세, 마이페이지 공용)
    ├─ ReviewEditor
    └─ SimilarBookByReviewCard  ← 신규, BookCard와 별도 컴포넌트로 분리
```

**분리 이유**: `BookCard`는 표지+제목+작가+태그만 다루는 범용 카드지만, `SimilarBookByReviewCard`는 인용문+유사 이유라는 리뷰 상세 전용 정보를 추가로 그린다. `BookCard`에 옵셔널 props를 얹어 억지로 겸용하면 다른 화면에서 불필요한 분기가 생기므로 별도 컴포넌트로 둔다.

**스타일 파일**: `/styles/tokens.css`에 색상·spacing·radius를 CSS 변수로 선언(`--color-primary`, `--space-4` 등)하고, 각 컴포넌트는 `className` + 해당 변수를 참조하는 plain CSS(`Button.css` 등 컴포넌트별 파일 또는 `app.css` 하나로 통합) 사용. Tailwind 클래스는 쓰지 않는다.

---

## 8. Day 12 완료 정의 (Definition of Done)

- [ ] 섹션 3의 화면 흐름도대로 모든 화면이 클릭으로 연결됨
- [ ] 섹션 6의 모든 화면이 명세된 레이아웃/상태/빈 상태까지 구현됨
- [ ] 리뷰 상세의 신규 섹션(6.8)이 규칙(본인 리뷰 포함, 다른 책만 추천, 빈 상태 처리)을 전부 만족
- [ ] `/hooks`의 모든 함수가 섹션 5.2 명세와 동일한 시그니처를 가짐 (다음 단계 API 교체를 위한 전제조건)
- [ ] 컴포넌트가 데이터를 직접 fetch하지 않고 훅을 통해서만 받음 (섹션 2 원칙 위반 없음)

---

## 9. Claude Code 요청 문구 예시

```
"UI_DESIGN_SPEC.md 섹션 5.1의 타입과 섹션 5.2의 훅 명세를 기준으로
/types와 /hooks를 전부 생성해줘. 지금은 /mock의 JSON을 읽어 반환하도록 구현해줘."

"섹션 6.8의 리뷰 상세 화면을 구현해줘. 신규 섹션의 SimilarBookByReviewCard는
섹션 7에서 별도 컴포넌트로 분리하라고 한 대로 review/ 폴더에 새로 만들어줘."

"섹션 8의 Definition of Done 체크리스트를 기준으로 지금까지 구현된 화면들을
점검하고, 빠진 항목이 있으면 알려줘."
```
