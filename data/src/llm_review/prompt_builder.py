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
  content의 각 문장은 구체적인 장면·감정·생각·비유를 담아 충분히 상세하게 쓰고, 단순한 사실 나열이나 5~8문장 짜리 짧은 요약형 리뷰는 금지.
  글을 다 쓴 후 스스로 분량이 800자에 못 미친다고 판단되면, 문장을 추가하거나 각 문장을 더 구체적으로 늘려써서 분량을 채운 뒤 출력할 것.
- 실제 독자가 개인 블로그나 SNS에 올린 솔직한 감상 톤으로 작성
- 작가의 다른 작품 제목 등 실제로 확인되지 않는 구체적 정보는 『X』, 『Y』 같은 placeholder로 쓰지 말고, "전작에서도" 처럼 제목을 특정하지 않는 방식으로 우회할 것
- 지금 리뷰하는 이 책의 제목에 문장부호가 필요할 경우 따옴표 정도만 사용할 것.
  개인 블로그·SNS 글에서는 책 제목에 부호(「」,『』) 없이 자연스럽게 언급하거나 필요하면 작은따옴표 정도만 쓴다.
  책 제목 뿐만 아니어도 「」,『』 문장부호는 절대로 사용하지 말 것. 이를 절대로 어겨서는 안된다.
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
아래는 위 페르소나·sentiment로 작성했던 리뷰인데 분량이 부족해서 다시 써야 해.

[이전 작성본 - 분량 부족(공백 포함 {prev_length}자)]
{prev_content}

이전 작성본의 관점과 어조는 유지하되, 장면·감정·생각·비유를 더 구체적으로 늘려 쓰고
단순 요약이나 문장 나열로 분량만 채우지 말 것. 이전 작성본을 그대로 복사하지 말고
실제로 더 상세하게 다시 써서 완성할 것.
반드시 공백 포함 {min_length}자 이상이 되도록 작성할 것. 이는 가장 중요한 조건이다.
글을 다 쓴 후 스스로 분량이 {min_length}자에 못 미친다고 판단되면, 문장을 추가하거나
각 문장을 더 구체적으로 늘려써서 분량을 채운 뒤 출력할 것.
실제 독자가 개인 블로그나 SNS에 올린 솔직한 감상 톤으로 작성.
작가의 다른 작품 제목 등 실제로 확인되지 않는 구체적 정보는 『X』, 『Y』 같은 placeholder로
쓰지 말고, "전작에서도" 처럼 제목을 특정하지 않는 방식으로 우회할 것.
지금 리뷰하는 이 책의 제목도 『{title}』, 「{title}」 같은 격식체 서명 부호로 감싸지 말 것.
개인 블로그·SNS 글에서는 책 제목을 그런 부호 없이 자연스럽게 언급하거나 필요하면 작은따옴표 정도만 쓴다.
같은 리뷰 안에서 제목을 여러 번 언급하더라도 표기 방식을 통일할 것.
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


def build_single_review_prompt(
    book: dict,
    persona: dict,
    sentiment: str,
    prev_content: str,
    few_shot_example: dict,
    min_length: int,
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
        min_length=min_length,
        few_shot_review=few_shot_example["content"].strip(),
    )
