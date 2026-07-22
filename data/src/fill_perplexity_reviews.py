"""
data/raw/perplexity_result.html(Notion에서 내보낸 퍼플렉시티 결과)을 파싱하여
0~87번 도서 순서대로 리뷰 본문을 추출하고, data/processed/books_naver.jsonl의
perplexity_review 필드를 채운다.

파싱 방식:
- HTML이 완전한 구조가 아니다 (예: 첫 코드블록 뒤 Prism 스크립트/링크 태그 삽입,
  27번 항목은 </li> 누락). 이 때문에 "번호 마커"와 "코드블록(리뷰 본문)"을
  각각 독립적으로 전체 문서에서 추출한 뒤, 둘 다 88개씩 순서대로 나온다는
  사실을 이용해 위치 순서로만 짝짓는다. (실제 인접 여부는 확인하지 않음)
- books_naver.jsonl의 줄 순서는 final_book_list_88.csv 행 순서와 동일하므로
  i번째 줄 <-> i번 리뷰로 그대로 매핑한다.
"""

import html
import json
import re
import sys
from pathlib import Path

HTML_PATH = Path(__file__).parent.parent / "raw" / "perplexity_result.html"
JSONL_PATH = Path(__file__).parent.parent / "processed" / "books_naver.jsonl"

MARKER_PATTERN = re.compile(r'<ol[^>]*\sstart="(\d+)"|<p[^>]*class=""[^>]*>(\d+)\.\s')
CODE_BLOCK_PATTERN = re.compile(
    r"<pre[^>]*>\s*<code[^>]*>(?P<content>.*?)</code>\s*</pre>", re.DOTALL
)


def extract_reviews(html_content: str) -> list[str]:
    markers = list(MARKER_PATTERN.finditer(html_content))
    indices = [int(m.group(1) or m.group(2)) for m in markers]
    if indices != list(range(len(indices))):
        raise ValueError(f"번호 마커가 0..N 순서가 아닙니다: {indices}")

    code_blocks = CODE_BLOCK_PATTERN.findall(html_content)

    if len(markers) != len(code_blocks):
        raise ValueError(
            f"마커 개수({len(markers)})와 코드블록 개수({len(code_blocks)})가 일치하지 않습니다."
        )

    return [html.unescape(content).strip() for content in code_blocks]


def main():
    html_content = HTML_PATH.read_text(encoding="utf-8")
    reviews = extract_reviews(html_content)
    print(f"[파싱 완료] 리뷰 {len(reviews)}건 추출", file=sys.stderr)

    with open(JSONL_PATH, encoding="utf-8") as f:
        records = [json.loads(line) for line in f]

    if len(records) != len(reviews):
        raise ValueError(
            f"jsonl 레코드 수({len(records)})와 리뷰 수({len(reviews)})가 일치하지 않습니다."
        )

    for record, review in zip(records, reviews):
        record["perplexity_review"] = review

    with open(JSONL_PATH, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"[완료] {len(records)}건에 perplexity_review 반영 -> {JSONL_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
