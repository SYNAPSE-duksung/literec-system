import csv
import sys
from pathlib import Path

CSV_PATH = Path(__file__).parent / "processed" / "final_book_list_88.csv"
OUTPUT_DIR = Path(__file__).parent / "processed" / "prompts"

PROMPT_TEMPLATE = '''{title}({author}, {publisher}, 판매상품 ID({isbn}))에 대해
다음 항목만 답해줘.

1. 이 책을 좋아한 독자들이 주로 언급한 이유 3가지 이상
2. 이 책을 별로라고 한 독자들이 주로 언급한 이유 3가지 이상
3. 최근 2년 이내의 전반적인 독자 반응에서 호 / 불호 / 혼재 리뷰 각각에서 제시한 근거를 나열하고 해당 리뷰들의 비율을 제시
4. 자주 언급되는 정서 키워드 3~5개
5. 평론/수상 등 외부 평가가 독자 반응에 영향을 미쳤다면 한 줄로 요약

- 줄거리 요약은 포함하지 마
- 결말이나 반전은 언급해도 되되, 직접적인 내용 공개는 피해줘
  (예: "결말이 열린 결말이라 호불호가 갈린다" 수준은 OK,
       "주인공이 ~한다" 식의 직접 서술은 제외)
- 출처는 블로그, 독서 커뮤니티, SNS, 문학 평론 모두 포함
- 1~2번은 일반 독자 반응 위주로, 5번에서 평론을 별도로 구분'''


def load_books(csv_path: Path) -> list[dict]:
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_prompt(book: dict) -> str:
    return PROMPT_TEMPLATE.format(
        title=book["상품명"],
        author=book["인물"],
        publisher=book["출판사"],
        isbn=book["판매상품 ID"],
    )


def generate_prompts(start: int, end: int) -> list[str]:
    books = load_books(CSV_PATH)
    if not (0 <= start <= end < len(books)):
        raise ValueError(f"인덱스 범위가 올바르지 않습니다. (0 ~ {len(books) - 1} 사이여야 함)")

    blocks = []
    for i in range(start, end + 1):
        book = books[i]
        header = f"[{i}] {book['상품명']} - {book['인물']}"
        blocks.append(f"{header}\n{build_prompt(book)}")
    return blocks


def main():
    if len(sys.argv) != 3:
        print("사용법: python generate_review_prompts.py <시작인덱스> <끝인덱스>")
        print("예시:   python generate_review_prompts.py 0 21")
        sys.exit(1)

    start, end = int(sys.argv[1]), int(sys.argv[2])
    blocks = generate_prompts(start, end)
    output = f"\n\n{'=' * 80}\n\n".join(blocks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"prompts_{start}_{end}.txt"
    out_path.write_text(output, encoding="utf-8")

    print(output)
    print(f"\n[저장 완료] {out_path} ({len(blocks)}개 프롬프트)", file=sys.stderr)


if __name__ == "__main__":
    main()
