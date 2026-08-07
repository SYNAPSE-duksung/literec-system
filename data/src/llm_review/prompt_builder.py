"""
personas.yaml에서 페르소나 정의를 불러와 책 정보/Perplexity 검색 결과와 함께
LLM 리뷰 생성 프롬프트를 조립한다.

출력 형식 지시는 원본(사람이 읽는 "리뷰 1 / - 페르소나: ..." 텍스트) 대신
JSON 스키마로 대체했다. review_index/isbn/book_title은 LLM에 맡기지 않고
generate_llm_reviews.py에서 채운다.
"""

from pathlib import Path

import yaml

PERSONAS_PATH = Path(__file__).parent / "personas.yaml"
FEW_SHOT_PATH = Path(__file__).parent / "few_shot_example.yaml"

FORBIDDEN_BRACKETS = "『』「」"


def has_forbidden_brackets(text: str) -> bool:
    return any(ch in text for ch in FORBIDDEN_BRACKETS)

PROMPT_TEMPLATE = """[책 정보]
- 제목: {title}
- 작가: {author}
- 출판사: {publisher}
- ISBN: {isbn}
- 책 소개: {description}

[Perplexity 검색 결과]
{perplexity_review}

[페르소나 정의]
{persona_block}

---

[지시사항]

위 책 정보와 독자 평판 요약을 바탕으로 리뷰 5개를 생성해줘.

구성:
- reviews 배열의 순서대로 다음 sentiment를 정확히 배정할 것 (이 순서와 값을 반드시 지킬 것):
  1번째 리뷰 = 호, 2번째 리뷰 = 호, 3번째 리뷰 = 불호, 4번째 리뷰 = 불호, 5번째 리뷰 = 혼재

페르소나 배정:
- persona 필드에는 반드시 다음 6개 이름 중 하나를 글자 그대로(변형·조합·신규 이름 금지)
  써야 해: 감정 몰입형, 문체 분석형, 빠른 소비형, 맥락 탐구형, 추천받고 읽은 독자, 재독자
- 이 책에 가장 적합한 페르소나를 리뷰마다 하나씩 선택해줘.
- 이 페르소나로 선택한 이유를 리뷰 생성 전에 한 줄로 밝혀줘.
- 5개 리뷰 내에서 동일한 페르소나 중복 사용 금지.

각 리뷰 본문 작성 조건:
- 길이: 반드시 800자 이상 (공백 포함, 페르소나마다 편차를 줄 것). 800자에 못 미치면 안 됨.
  이는 매우 중요한 조건이며, 짧게 쓰는 것보다 우선한다.
  content의 각 문장은 구체적인 장면·감정·생각을 담아 충분히 상세하게 쓰고, 단순한 사실 나열이나 5~8문장 짜리 짧은 요약형 리뷰는 금지.
  글을 다 쓴 후 스스로 분량이 800자에 못 미친다고 판단되면, 문장을 추가하거나 각 문장을 더 구체적으로 늘려써서 분량을 채운 뒤 출력할 것.
- 비유는 꼭 필요할 때 한두 번만 아껴서 쓸 것. 같은 감정이나 장면을 표현만 바꿔가며 여러 비유로
  반복 서술하지 말고, 불필요하게 장황하거나 과장된 비유·수식어는 줄이고 구체적인 사실과 생각
  위주로 담백하게 쓸 것. 분량은 비유를 늘려서가 아니라 다루는 내용(장면, 이유, 생각)을
  늘려서 채울 것.
- 실제 독자가 개인 블로그나 SNS에 올린 솔직한 감상 톤으로 작성
- 작가의 다른 작품 제목 등 실제로 확인되지 않는 구체적 정보는 특정 제목을 꾸며내지 말고, "전작에서도" 처럼 제목을 특정하지 않는 방식으로 우회할 것
- 책 제목(지금 리뷰하는 책이든 다른 책이든)을 겹낫표(『 』)나 홑낫표(「 」) 같은 격식체 인용부호로 감싸지 말 것.
  개인 블로그·SNS 글에서는 책 제목을 그런 부호 없이 자연스럽게 언급하거나 필요하면 작은따옴표 정도만 쓴다.
  겹낫표·홑낫표는 이 리뷰 어디에도 절대 사용하지 말 것. 이를 절대로 어겨서는 안된다.
- 글자가 깨지거나(예: □, �, 알아볼 수 없는 기호) 실제로 존재하지 않는 이상한 유니코드 문자가 절대 섞여 들어가지 않도록 할 것.
  정상적인 한글·영문·숫자·일반적인 문장부호만 사용하고, 출력 전에 이상한 문자가 없는지 스스로 검토할 것.
- 결말이나 반전의 직접적인 내용 공개 금지
  (예: "결말이 열린 결말이라 여운이 남는다" 수준은 OK, "주인공이 ~한다" 식의 직접 서술은 금지)
- 아래 5개 축 중 3개 이상을 자연스럽게 포함할 것(요소를 명시하지 말고 내용에 자연스럽게 포함되도록):
    ① 정서_경험: 읽고 난 후 느낀 감정
    ② 좋았던_요소: 문체/구성/결말 등 형식적 호평
    ③ 별로였던_요소: 아쉬웠던 형식적 요소
    ④ 소재_및_주제: 줄거리·소재 자체에 대한 반응
    ⑤ 독서_경험_맥락: 몰입도, 재독 여부 등
- LLM 특유의 '**'같은 볼드 체와 마크다운 형식을 쓰지 말고 그냥 텍스트 형식으로 작성

[예시 - 리뷰 본문 하나, 분량·문체·형식 참고용]
아래는 참고용으로 제공되는 리뷰 본문 예시이다. 실제 답변에 이 내용을 그대로 쓰거나 언급하지 말고, 길이·문장 수·톤만 참고할 것.

{few_shot_review}

- 위 예시처럼 개인적인 감상이 드러나도록 작성할 것.
- 또한, 확정적인 어투보다는 ~라 생각한다, ~라고 봤다 같은 개인적인 기록 느낌으로 작성할 것.

출력 형식:
아래 JSON 형식으로만 출력할 것. 다른 설명, 마크다운, 코드블록 표시 없이 JSON 객체 하나만 출력.
{{
  "reviews": [
    {{
      "persona": "(선택한 페르소나명)",
      "persona_reason": "(선택 이유, 한 줄)",
      "sentiment": "호 또는 불호 또는 혼재 중 하나",
      "content": "(리뷰 본문)"
    }},
    ... 총 5개
  ]
}}
"""


def load_personas(yaml_path: Path = PERSONAS_PATH) -> list[dict]:
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["personas"]


def load_few_shot_example(yaml_path: Path = FEW_SHOT_PATH) -> dict:
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def format_persona_block(personas: list[dict]) -> str:
    blocks = []
    for i, persona in enumerate(personas, start=1):
        blocks.append(
            f"{i}. {persona['name']}\n"
            f"{persona['description'].strip()}\n"
            f"(작성 톤: {persona['tone'].strip()})"
        )
    return "\n\n".join(blocks)


def build_prompt(book: dict, personas: list[dict], few_shot_example: dict) -> str:
    return PROMPT_TEMPLATE.format(
        title=book["title"],
        author=book["author"],
        publisher=book["publisher"],
        isbn=book["isbn"],
        description=book["description"],
        perplexity_review=book["perplexity_review"],
        persona_block=format_persona_block(personas),
        few_shot_review=few_shot_example["content"].strip(),
    )


SINGLE_REVIEW_PROMPT_TEMPLATE = """[책 정보]
- 제목: {title}
- 작가: {author}
- 출판사: {publisher}
- ISBN: {isbn}
- 책 소개: {description}

[Perplexity 검색 결과]
{perplexity_review}

[페르소나 - 반드시 이 페르소나를 유지할 것, 변경 금지]
{persona_name}
{persona_description}
(작성 톤: {persona_tone})

[sentiment - 반드시 이 값을 유지할 것, 변경 금지]
{sentiment}

---

[지시사항]
아래는 위 페르소나·sentiment로 작성했던 리뷰인데, 다음 문제가 있어서 다시 써야 해:
{issue_description}

[이전 작성본 - 공백 포함 {prev_length}자]
{prev_content}

이전 작성본의 관점과 어조는 유지하되, 위에 나열된 문제만 확실히 고쳐서 다시 쓸 것.
장면·감정·생각을 더 구체적으로 늘려 쓰고, 단순 요약이나 문장 나열로 분량만 채우지 말 것.
비유는 꼭 필요할 때 한두 번만 아껴서 쓰고, 같은 감정을 여러 비유로 반복 서술하지 말 것.
분량은 비유를 늘려서가 아니라 다루는 내용(장면, 이유, 생각)을 늘리거나 줄여서 맞출 것.
이전 작성본을 그대로 복사하지 말고 실제로 다시 써서 완성할 것.
반드시 공백 포함 {min_length}자 이상 {max_length}자 이하가 되도록 작성할 것
(목표 범위: {min_length}~{max_length}자). 이는 가장 중요한 조건이다.
{min_length}자에 못 미치면 문장을 추가하거나 각 문장을 더 구체적으로 늘려 분량을 채우고,
반대로 {max_length}자를 넘길 것 같으면 문장을 덜어내거나 늘어지는 부분을 줄여서
반드시 {max_length}자 이내로 맞춘 뒤 출력할 것. 상한선을 넘기는 것은 하한선을 못 채우는
것만큼 심각한 실패다.
실제 독자가 개인 블로그나 SNS에 올린 솔직한 감상 톤으로 작성.
작가의 다른 작품 제목 등 실제로 확인되지 않는 구체적 정보는 특정 제목을 꾸며내지 말고,
"전작에서도" 처럼 제목을 특정하지 않는 방식으로 우회할 것.
책 제목(지금 리뷰하는 책이든 다른 책이든)을 겹낫표(『 』)나 홑낫표(「 」) 같은 격식체
인용부호로 감싸지 말 것. 개인 블로그·SNS 글에서는 책 제목을 그런 부호 없이 자연스럽게
언급하거나 필요하면 작은따옴표 정도만 쓴다. 겹낫표·홑낫표는 이 리뷰 어디에도 절대
사용하지 말 것. 같은 리뷰 안에서 제목을 여러 번 언급하더라도 표기 방식을 통일할 것.
글자가 깨지거나(예: □, �, 알아볼 수 없는 기호) 실제로 존재하지 않는 이상한 유니코드 문자가
절대 섞여 들어가지 않도록 할 것. 정상적인 한글·영문·숫자·일반적인 문장부호만 사용하고,
출력 전에 이상한 문자가 없는지 스스로 검토할 것.
결말이나 반전의 직접적인 내용 공개 금지.
LLM 특유의 '**'같은 볼드체와 마크다운 형식을 쓰지 말고 그냥 텍스트 형식으로 작성.

[예시 - 분량·문체·형식 참고용, 내용은 언급하지 말 것]
{few_shot_review}

출력 형식:
아래 JSON 형식으로만 출력할 것. 다른 설명, 마크다운, 코드블록 표시 없이 JSON 객체 하나만 출력.
{{
  "content": "(다시 쓴 리뷰 본문)"
}}
"""


STRUCTURE_PROMPT_TEMPLATE = """아래는 같은 책 한 권에 대한 리뷰 {count}개(원문)이다. 각 리뷰를
5개 축으로 구조화해줘.

[리뷰 목록]
{reviews_block}

[5축 정의]
- 정서_경험: 읽고 난 후 느낀 감정 (예: 쓸쓸함, 위로받음, 먹먹함). 명시적인 감정 단어뿐
  아니라 암묵적으로 드러나는 반응(예: "당황했다", "온몸으로 느꼈다", "머리가 무거워졌다")도
  놓치지 말고 잡아낼 것.
- 좋았던_요소: 문체, 구성, 결말 등 형식적/스타일적 호평
- 별로였던_요소: 아쉬웠던 형식적/스타일적 요소
- 소재_및_주제: 줄거리·소재 자체에 대한 반응
- 독서_경험_맥락: 몰입도, 재독 여부 등 선택적 부가 정보

[작업 방식]
1. 각 리뷰의 content를 읽고, 각 축에 실제로 언급된 내용(명시적 표현뿐 아니라 암묵적으로
   드러나는 반응까지 포함)이 있으면 리뷰어의 표현을 살리되 1~2문장으로 간결하게 요약/추출해서
   채운다. 원문을 그대로 길게 복사하지 말 것.
2. 리뷰에 해당 축 내용이 전혀 없으면 억지로 채우지 말고 null로 둔다.
3. sentiment(라벨)는 여기서 다루지 않는다 — 절대 새로 판단하거나 출력하지 말 것 (호출부가
   원본 값을 그대로 사용한다).

출력 형식:
아래 JSON 형식으로만 출력할 것. 다른 설명, 마크다운, 코드블록 표시 없이 JSON 객체 하나만 출력.
{{
  "reviews": [
    {{
      "review_index": (원본 review_index 정수 그대로),
      "정서_경험": "..." 또는 null,
      "좋았던_요소": "..." 또는 null,
      "별로였던_요소": "..." 또는 null,
      "소재_및_주제": "..." 또는 null,
      "독서_경험_맥락": "..." 또는 null
    }},
    ... 입력 순서·review_index 그대로 유지하며 총 {count}개
  ]
}}
"""


def format_reviews_block(reviews: list[dict]) -> str:
    blocks = []
    for review in reviews:
        blocks.append(
            f"--- 리뷰 {review['review_index']} (sentiment: {review['sentiment']}) ---\n"
            f"{review['content']}"
        )
    return "\n\n".join(blocks)


def build_structure_prompt(reviews: list[dict]) -> str:
    return STRUCTURE_PROMPT_TEMPLATE.format(
        count=len(reviews),
        reviews_block=format_reviews_block(reviews),
    )


def describe_content_issues(content: str, min_length: int, max_length: int) -> str:
    length = len(content)
    issues = []
    if length < min_length:
        issues.append(f"- 분량이 부족함 ({length}자, {min_length}자 이상이어야 함)")
    elif length > max_length:
        issues.append(f"- 분량이 너무 김 ({length}자, {max_length}자 이하여야 함)")
    if has_forbidden_brackets(content):
        issues.append(
            "- 겹낫표(『 』)나 홑낫표(「 」) 같은 격식체 인용부호가 포함되어 있음"
            " (이번에는 절대 쓰지 말 것)"
        )
    return "\n".join(issues) if issues else "- (분량은 적정 범위이나 다른 사유로 재작성 요청됨)"


def build_single_review_prompt(
    book: dict,
    persona: dict,
    sentiment: str,
    prev_content: str,
    few_shot_example: dict,
    min_length: int,
    max_length: int,
) -> str:
    return SINGLE_REVIEW_PROMPT_TEMPLATE.format(
        title=book["title"],
        author=book["author"],
        publisher=book["publisher"],
        isbn=book["isbn"],
        description=book["description"],
        perplexity_review=book["perplexity_review"],
        persona_name=persona["name"],
        persona_description=persona["description"].strip(),
        persona_tone=persona["tone"].strip(),
        sentiment=sentiment,
        prev_length=len(prev_content),
        prev_content=prev_content,
        issue_description=describe_content_issues(prev_content, min_length, max_length),
        min_length=min_length,
        max_length=max_length,
        few_shot_review=few_shot_example["content"].strip(),
    )
