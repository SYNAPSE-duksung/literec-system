// Access token은 새로고침 시 사라지는 게 정상 동작(보안상 localStorage에 저장하지 않음).
// React state가 아니라 모듈 스코프 변수로 두고, apiClient가 매 요청마다 동기적으로 읽는다.
let accessToken: string | null = null;
let currentUserId: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getCurrentUserId(): string | null {
  return currentUserId;
}

export function setCurrentUserId(userId: string | null): void {
  currentUserId = userId;
}

export function clearAuth(): void {
  accessToken = null;
  currentUserId = null;
}
