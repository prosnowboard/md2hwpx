# Markdown to HWPX 변환 테스트 문서

## 1. 기본 텍스트

이 문서는 Markdown에서 HWPX로의 변환을 테스트하기 위한 샘플입니다.
한글(Hangul)과 English가 혼합된 문서입니다.

### 1.1 인라인 서식

**굵은 글씨(Bold)**와 *기울임(Italic)* 그리고 ~~취소선(Strikethrough)~~을 지원합니다.
또한 `인라인 코드`도 지원합니다.
***굵은 기울임***도 가능합니다.

#### 1.1.1 중첩 서식

*이탤릭 안에 **굵은 글씨** 포함*

##### 1.1.2 작은 제목

작은 제목도 지원합니다.

###### 1.1.3 가장 작은 제목 (H6)

H6까지 모두 지원합니다.

---

## 2. 리스트

### 비순서 리스트

- 첫 번째 항목
- 두 번째 항목
  - 중첩된 항목 A
  - 중첩된 항목 B
    - 더 깊은 중첩
- 세 번째 항목

### 순서 리스트

1. 첫 번째 단계
2. 두 번째 단계
   1. 세부 단계 2-1
   2. 세부 단계 2-2
3. 세 번째 단계

### 체크박스(Task List)

- [x] 완료된 작업
- [ ] 미완료 작업
- [x] 또 다른 완료된 작업

---

## 3. 코드 블록

Python 코드 예시:

```python
def convert_md_to_hwpx(input_path: str, output_path: str) -> None:
    """Markdown 파일을 HWPX로 변환합니다."""
    with open(input_path, 'r', encoding='utf-8') as f:
        markdown_text = f.read()
    # 변환 로직
    print(f"변환 완료: {output_path}")
```

언어 지정 없는 코드 블록:

```
plain text code block
no language specified
```

## 4. 표(Table)

| 이름 | 나이 | 직업 |
|:-----|:----:|-----:|
| 홍길동 | 30 | 개발자 |
| 김영희 | 25 | 디자이너 |
| 이철수 | 35 | 매니저 |

## 5. 인용문(Blockquote)

> 이것은 인용문입니다.
>
> 여러 단락의 인용문도 가능합니다.

> 외부 인용문
>
> > 중첩된 인용문

## 6. 링크와 이미지

[GitHub](https://github.com "GitHub 홈페이지")를 방문하세요.

![샘플 이미지](https://example.com/image.png "이미지 제목")

## 7. 각주(Footnotes)

HWPX는 한컴오피스의 문서 형식입니다[^1].
OWPML은 개방형 워드프로세서 마크업 언어입니다[^2].

[^1]: HWPX는 XML 기반의 현대적인 문서 형식입니다.
[^2]: OWPML은 KS X 6101 국가 표준입니다.

---

## 8. 줄바꿈

이것은 첫 번째 줄입니다.  
이것은 두 번째 줄입니다 (하드 브레이크).

***
