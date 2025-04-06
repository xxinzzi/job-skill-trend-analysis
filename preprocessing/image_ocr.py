# GPT-4o Vision 기반 이미지 OCR 모듈
import openai
import os
from dotenv import load_dotenv

# Load .env 파일에 저장된 OPENAI_API_KEY
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def extract_job_text_from_image(image_url: str) -> str:
    """
    GPT-4o Vision API를 사용해 채용 공고 이미지에서 텍스트 추출
    :param image_url: 이미지 URL (원본 또는 Firebase URL 등)
    :return: 추출된 텍스트 (실패 시 None)
    """
    try:
        print(f"이미지 텍스트 추출 시도 중...\nURL: {image_url}")

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant who extracts all visible Korean text from images "
                        "such as job postings, and returns the full content in plain text."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "채용 공고 이미지에서 모든 텍스트를 추출해 줘."},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            max_tokens=1500
        )

        extracted = response.choices[0].message.content.strip()
        return extracted if extracted else None

    except Exception as e:
        print(f"❌ GPT-4o Vision OCR 실패: {e}")
        return None
