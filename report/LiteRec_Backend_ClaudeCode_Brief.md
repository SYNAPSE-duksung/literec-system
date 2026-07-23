# LiteRec 백엔드 구현 요청 — Claude Code 작업 지시서

> 이 문서는 Claude Code에게 그대로 전달할 작업 브리프입니다.
> 현재 상태: React + Vite 프론트엔드는 목업 UI만 존재 (mock 데이터, 로그인/저장 로직 없음)
> 목표: FastAPI 백엔드 신규 구현 + 프론트 mock → 실제 API 연동
>
> ※ 오프라인 평가용 데이터셋/라벨링 기능은 이번 스코프에서 제외 (별도 구글폼으로 수집).
>   이 문서는 순수하게 **서비스 UI가 실제로 동작하기 위한 백엔드**만 다룹니다.

---

## 0. 컨텍스트 요약

- 레포: `literec-system` (모노레포, `app/` 프론트 + `backend/` FastAPI + `ML/`, `data/`)
- 프론트는 이미 `/hooks` 디렉토리에 `useBooks()`, `useBook(bookId)`, `useRecommendations()`, `useReviews(filter?)`, `useReviewsByBook(bookId)`, `useReview(reviewId)`, `useUserProfile()`, `useSimilarReviewBooks(reviewId)` 형태로 훅이 정의되어 있고, 모두 `{ data, isLoading, isError }`를 반환하도록 설계되어 있음 → **mock 데이터를 실제 fetch로 교체하는 구조로 설계되어 있으므로 훅 시그니처는 유지**
- 화면 목록: login, signup, onboarding(2 Step), home, bookDetail, board, reviewWrite, reviewDetail, search, mypage
- 추천 알고리즘 자체(임베딩/클러스터링/XAI)는 별도 ML 파트에서 별도 진행 중이므로 이번 스코프에서 제외. 추천 API는 **완전 랜덤 N권을 반환하는 더미**로만 연결

---

## 1. 이번 스프린트 스코프

### 포함 (Do)
1. 회원가입 / 로그인 / 로그아웃 (Access + Refresh Token)
2. 온보딩 데이터 저장 (선호 정서 7개 중 선택, 부담 요소 5개 중 선택)
3. 유저 프로필 CRUD (`useUserProfile()` 연동)
4. 도서 목록/상세 API (88권 시드 데이터 기반)
5. 게시판 리뷰 CRUD (작성/조회/좋아요, 별도 검증·모더레이션 없이 저장만)
6. 추천 API 더미 (랜덤 N권 반환)
7. PostgreSQL 스키마 및 마이그레이션
8. 로컬 개발 환경 (docker-compose로 FastAPI + Postgres 기동)

### 제외 (Don't — 이번 스코프 아님)
- 추천 알고리즘 실제 로직 (ML 파트 별도 진행)
- 벡터 임베딩/FAISS 연동
- 오프라인 평가용 라벨링 데이터 수집 (구글폼으로 별도 진행)
- K8s 매니페스트 배포 (인프라 담당자 별도 진행)
- CronJob (일/주 단위 재학습) 로직
- 소셜 로그인 (이메일/비밀번호만)
- 리뷰 콘텐츠 검증/모더레이션 (그냥 저장만, 필요 시 추후 추가)

---

## 2. 기술 스택 (기존 결정 준수)

- **Backend**: FastAPI, Python, `uv` 패키지 관리
- **DB**: PostgreSQL (SQLAlchemy + Alembic 마이그레이션 권장)
- **Auth**: JWT Access + Refresh Token 방식
  - Access token: 만료 15~30분, 요청마다 Authorization 헤더로 검증
  - Refresh token: 만료 1~2주, DB에 저장(로그아웃/탈취 시 무효화 가능하도록), httpOnly 쿠키 또는 별도 저장소 — 프론트 구현 방식에 맞춰 Claude Code가 제안하되 **보안상 localStorage에 refresh token 직접 저장은 지양**
  - Access token 만료 시 `/api/auth/refresh`로 재발급
- **비밀번호 해시**: bcrypt (passlib)
- **Data files**: `data/processed/books_enriched.json` (88건, book 메타 + perplexity_raw), `data/processed/reviews.json` (isbn 외래키, 440건) — 이 두 파일을 초기 시드 데이터로 DB에 적재

---

## 3. DB 스키마 초안

```
users
- id (uuid, pk)
- email (unique, nullable)          -- 카카오 로그인 시 이메일 미동의 가능성 있어 nullable
- password_hash (nullable)          -- 카카오 전용 유저는 null (비밀번호 없음)
- name
- auth_provider (enum: 'local' | 'kakao', default 'local')
- provider_id (text, nullable)      -- 카카오가 발급하는 고유 유저 ID
- created_at
-- (auth_provider, provider_id) unique 조합으로 동일 카카오 계정 중복 가입 방지

refresh_tokens
- id (uuid, pk)
- user_id (fk → users.id)
- token_hash            -- 원문 저장 금지, 해시로 저장
- expires_at
- revoked (boolean, default false)
- created_at

user_profiles
- user_id (fk → users.id, unique)
- preferred_emotions (text[])   -- 온보딩 Step1, 7개 중 선택
- avoided_traits (text[])       -- 온보딩 Step2, 5개 중 선택
- updated_at

books
- isbn (pk)
- title
- author
- publisher
- cover_url          -- 네이버 도서 API 값
- synopsis
- created_at

book_aspects            -- LLM이 리뷰에서 추출한 5개 축 구조화 데이터 (책 단위 대표값, IdentityRadarChart용)
- isbn (fk → books.isbn)
- emotion_experience (text[])   -- 정서_경험
- liked_elements (text[])       -- 좋았던_요소
- disliked_elements (text[])    -- 별로였던_요소
- themes (text[])               -- 소재_및_주제
- reading_context (text[])      -- 독서_경험_맥락
- updated_at

reviews
- id (uuid, pk)
- isbn (fk → books.isbn)
- user_id (fk → users.id, nullable)  -- LLM 생성 리뷰는 null, 실사용자는 user_id 존재
- source (enum: 'llm_generated' | 'user')
- persona (text, nullable)      -- LLM 생성 리뷰인 경우만
- content (text)
- emotion_tags (text[])
- liked_points (text[])
- disliked_points (text[])
- like_count (int, default 0)
- dislike_count (int, default 0)
- created_at

review_reactions         -- 리뷰에 대한 좋아요/싫어요 (UI 목업 기준: 좋아요/싫어요 버튼 둘 다 존재)
- review_id (fk)
- user_id (fk)
- reaction (enum: 'like' | 'dislike')
- created_at
- (review_id, user_id) unique   -- 한 유저당 리뷰 하나에 반응 하나만 (좋아요/싫어요 상호 배타)

book_reactions           -- 책 자체에 대한 좋아요/싫어요 (리뷰 작성과 별개, mypage "좋아한 책" ❤️ 및 신규 👎 버튼)
- user_id (fk → users.id)
- isbn (fk → books.isbn)
- reaction (enum: 'like' | 'dislike')
- created_at
- (user_id, isbn) unique   -- 한 유저당 책 하나에 반응 하나만 (좋아요/싫어요 상호 배타)
```

```mermaid
erDiagram
    users ||--o{ refresh_tokens : "has"
    users ||--o| user_profiles : "has"
    users ||--o{ reviews : "writes"
    users ||--o{ review_reactions : "reacts"
    users ||--o{ book_reactions : "reacts"

    books ||--o| book_aspects : "has"
    books ||--o{ reviews : "has"
    books ||--o{ book_reactions : "receives"

    reviews ||--o{ review_reactions : "receives"

    users {
        uuid id PK
        string email
        string password_hash
        string name
        string auth_provider
        string provider_id
        timestamp created_at
    }

    refresh_tokens {
        uuid id PK
        uuid user_id FK
        string token_hash
        timestamp expires_at
        boolean revoked
        timestamp created_at
    }

    user_profiles {
        uuid user_id PK, FK
        array preferred_emotions
        array avoided_traits
        timestamp updated_at
    }

    books {
        string isbn PK
        string title
        string author
        string publisher
        string cover_url
        text synopsis
        timestamp created_at
    }

    book_aspects {
        string isbn PK, FK
        array emotion_experience
        array liked_elements
        array disliked_elements
        array themes
        array reading_context
        timestamp updated_at
    }

    reviews {
        uuid id PK
        string isbn FK
        uuid user_id FK
        string source
        string persona
        text content
        array emotion_tags
        array liked_points
        array disliked_points
        int like_count
        int dislike_count
        timestamp created_at
    }

    review_reactions {
        uuid review_id PK, FK
        uuid user_id PK, FK
        string reaction
        timestamp created_at
    }

    book_reactions {
        uuid user_id PK, FK
        string isbn PK, FK
        string reaction
        timestamp created_at
    }
```

---

## 4. API 엔드포인트 초안

### 4.1 인증
```
POST   /api/auth/signup         { email, password, name } → 201
POST   /api/auth/login          { email, password } → { access_token, refresh_token, user }
POST   /api/auth/refresh        { refresh_token } → { access_token }
POST   /api/auth/logout         (Bearer token) → refresh_token revoke 처리
GET    /api/auth/me             (Bearer token) → 현재 유저 정보

POST   /api/auth/kakao/callback { code } → 카카오 인가 코드 받아 토큰 교환 → 유저 조회/신규생성 → 우리 서비스 Access/Refresh Token 발급
                                  ⚠️ 로그인 이후 흐름(JWT 발급/갱신)은 이메일 로그인과 동일 로직 재사용
```
- 이메일 형식 검증, 중복 이메일 체크는 백엔드에서도 최소한 처리 (프론트 검증과 별개로)
- 카카오 로그인 유저는 `auth_provider='kakao'`로 저장, `password_hash`는 null

### 4.2 온보딩 / 프로필
```
POST   /api/onboarding          { preferredEmotions[], avoidedTraits[] } → user_profiles upsert
GET    /api/users/me/profile    → UserProfile (useUserProfile() 연동)
PATCH  /api/users/me/profile    → 부분 수정 (마이페이지에서 취향 재설정 등)
```

### 4.3 도서
```
GET    /api/books               → 88권 리스트 (useBooks())
GET    /api/books/{isbn}        → 상세 (useBook, book_aspects 포함하여 IdentityRadarChart 데이터 제공)
GET    /api/books/search?q=...  → search 화면용 실시간 필터
```

### 4.4 리뷰 / 게시판
```
GET    /api/reviews?filter=...        → useReviews(filter?)  (board 목록)
GET    /api/books/{isbn}/reviews      → useReviewsByBook(bookId)
GET    /api/reviews/{id}              → useReview(reviewId)
POST   /api/reviews                   { isbn, content, emotion[], liked[], disliked[] } → 유저 작성 리뷰, 검증 없이 저장
POST   /api/reviews/{id}/reaction     { reaction: 'like' | 'dislike' } → review_reactions upsert (상호 배타)
DELETE /api/reviews/{id}/reaction     → 반응 취소
```
- ⚠️ 기존 `POST /api/reviews/{id}/like` 대신 위 방식으로 통일 (UI 목업에 좋아요/싫어요 버튼 둘 다 존재하므로 book_reactions와 동일 패턴 사용)

### 4.4.1 책 자체 반응 (좋아요/싫어요) — 신규
```
POST   /api/books/{isbn}/reaction     { reaction: 'like' | 'dislike' } → book_reactions upsert
                                       ⚠️ 리뷰 작성과 무관하게 독립적으로 남길 수 있는 반응
                                       ⚠️ 이미 반대 반응이 있으면 덮어씀 (좋아요↔싫어요 상호 배타)
DELETE /api/books/{isbn}/reaction     → 반응 취소 (중립 상태로)
GET    /api/users/me/liked-books      → mypage "좋아한 책" 목록 (useUserProfile 또는 별도 훅에서 사용)
```
- UI: bookDetail/mypage의 기존 ❤️(좋아요)는 그대로 유지, 옆에 👎 아이콘 신규 추가. 찜하기(북마크)는 이번 스코프에서 별도 구현하지 않음

### 4.5 추천 (더미)
```
GET    /api/recommendations           → useRecommendations()
                                         ⚠️ 완전 랜덤 N권 반환 (N=쿼리파라미터, 기본 10)
                                         ⚠️ ML 파트 연동 시 교체 예정임을 코드 주석에 명시
GET    /api/reviews/{id}/similar-books → useSimilarReviewBooks(reviewId)
                                         ⚠️ 동일하게 랜덤 더미
```

---

## 5. 프론트 연동 가이드

- 기존 `/hooks` 파일들은 목업 데이터를 반환하는 구조로 되어 있을 것 → 내부 구현만 실제 fetch로 교체, **훅의 반환 타입(`{ data, isLoading, isError }`)과 시그니처는 그대로 유지**해서 화면 컴포넌트 쪽 수정 최소화
- Access token: 메모리 또는 상태 관리 라이브러리에 저장, API 요청 시 Authorization 헤더 자동 첨부하는 공통 fetch wrapper 작성
- Refresh token: httpOnly 쿠키 권장 (프론트에서 직접 접근 불필요, 자동 전송) — 쿠키 방식이 부담되면 최소한 localStorage 대신 메모리+재로그인 유도 방식 검토
- Access token 만료로 401 응답 시, 공통 wrapper에서 자동으로 `/api/auth/refresh` 호출 후 원래 요청 재시도하는 인터셉터 패턴 구현

---

## 6. 시드 데이터 적재

- `data/processed/books_enriched.json` (88건) → `books` + `book_aspects` 테이블
- `data/processed/reviews.json` (440건) → `reviews` 테이블 (`source='llm_generated'`)
- 마이그레이션/시드용 1회성 스크립트는 `backend/scripts/seed.py` 형태로 분리, 반복 실행해도 중복 적재되지 않도록 upsert 처리

---

## 7. 작업 순서 제안 (Claude Code에게)

1. `backend/` 프로젝트 구조 설정 (FastAPI + uv + SQLAlchemy + Alembic)
2. DB 스키마 (섹션 3) → Alembic 마이그레이션 작성
3. 인증 (signup/login/refresh/logout) 구현 + 테스트
4. 온보딩/프로필 API 구현
5. 도서 시드 데이터 적재 스크립트 + 도서 GET API들
6. 리뷰 CRUD API 구현
7. 추천 API 더미(랜덤) 구현
8. 프론트 훅 실제 API 연동 (mock 제거, 공통 fetch wrapper + 토큰 갱신 인터셉터 포함)
9. docker-compose로 로컬 통합 테스트 (FastAPI + Postgres)

---

## 8. 결정된 사항 요약 (Claude Code가 임의로 되돌리지 않도록 명시)

| 항목 | 결정 |
|---|---|
| 추천 API 더미 로직 | 완전 랜덤 N권 (온보딩/태그 매칭 등 로직 없음, ML 파트 완성 전까지 임시) |
| 로그인 세션 | Access + Refresh Token, access 15~30분 / refresh 1~2주, refresh는 DB에 저장해 무효화 가능하도록 |
| 리뷰 작성 검증 | 별도 금칙어/길이 검증 없이 그냥 저장 (추후 필요 시 추가) |
| 오프라인 평가 데이터 | 이번 백엔드 스코프에서 완전히 제외, 별도 구글폼으로 수집 |
| 카카오 로그인 | `users` 테이블에 `auth_provider`/`provider_id` 필드로 확장 (옵션 A, 별도 oauth_accounts 테이블 아님). 지금 당장 카카오 로그인 기능 자체를 구현하진 않지만, 스키마는 미리 확장 가능하게 반영 |
| 책 자체 좋아요/싫어요 | 리뷰 반응(`review_reactions`)과 별개로 `book_reactions` 테이블 신규. UI는 기존 ❤️(좋아요) 유지 + 👎(싫어요) 아이콘 추가, 상호 배타적 토글. 찜하기(북마크)는 이번 스코프 제외. 오프라인 평가(별도 팀원 이슈)의 positive/negative 신호로 활용 예정 |
| 리뷰 좋아요/싫어요 | UI 목업(reviewDetail)에 좋아요/싫어요 버튼 둘 다 존재 확인됨 → `review_likes`를 `review_reactions`(reaction: like\|dislike)로 확장, book_reactions와 동일 패턴으로 통일. `reviews.dislike_count` 필드 추가 |