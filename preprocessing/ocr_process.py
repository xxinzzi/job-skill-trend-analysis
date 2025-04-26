import os
import sys
import asyncio
import aiohttp
from dotenv import load_dotenv
from google.cloud import vision
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timezone

# 경로 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.mongo_utils import init_mongo, get_collection

# 환경 변수 로드 및 인증 경로 설정
load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Google Vision API 클라이언트
vision_client = vision.ImageAnnotatorClient()

# MongoDB 연결
db = init_mongo()
if db is None:
    exit(1)

#src_col = get_collection("raw_postings_jobkorea")
src_col = get_collection("postings_deduplicated")
dst_col = get_collection("postings_with_ocr")
fail_log_col = get_collection("ocr_fail_logs")

# OCR 수행 함수
async def fetch_and_ocr(session, url):
    try:
        async with session.get(url, timeout=10) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}")
            content = await response.read()
            image = vision.Image(content=content)
            result = vision_client.text_detection(image=image)
            texts = result.text_annotations
            return texts[0].description.strip() if texts else ""
    except Exception:
        return None

# 각 문서에 대해 OCR 처리
async def process_doc(doc):
    ocr_results = []
    failed_urls = []

    # image_urls 가져오면서 바로 이상한 경우 처리
    image_urls = doc.get("image_urls")
    
    if not image_urls or not isinstance(image_urls, list):
        # NaN이거나, 빈 리스트거나, 리스트 타입 아니면 그냥 처리
        if not isinstance(image_urls, list):
            print(f"‼️ 비정상 image_urls 타입 발견, 무시: {doc.get('title', '제목 없음')}")
        
        doc["ocr_text"] = ""
        doc["has_ocr"] = False
        doc["ocr_processed_at"] = datetime.now(timezone.utc)
        dst_col.insert_one(doc)
        return  # OCR 시도 없이 바로 저장하고 끝

    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        for url in image_urls:
            try:
                text = await fetch_and_ocr(session, url)
                if text:
                    ocr_results.append(text)
            except Exception as e:
                print(f"❌ OCR 실패 - {url}: {e}")
                failed_urls.append({"url": url, "error": str(e)})

    # OCR 결과 병합 및 저장
    doc["ocr_text"] = "\n\n".join(ocr_results) if ocr_results else ""
    doc["has_ocr"] = bool(ocr_results)
    doc["ocr_processed_at"] = datetime.now(timezone.utc)

    dst_col.insert_one(doc)

    # 실패한 URL 로그 저장
    for fail in failed_urls:
        fail_log_col.insert_one({
            "source_id": doc.get("_id"),
            "url": fail["url"],
            "error": fail["error"],
            "timestamp": datetime.now(timezone.utc)
        })

    print(f"✅ OCR 완료: {doc.get('title', '제목 없음')} @ {doc.get('company', '회사 없음')}")

# 전체 실행
async def main():
    # postings_with_ocr에 _id가 없는 문서만 처리
    ocr_done_ids = dst_col.distinct("_id")
    docs = list(src_col.find({
        "_id": {"$nin": ocr_done_ids},
        "source": {"$ne": "saramin"}  # source가 saramin이 아닌 것만
    }))

    # 순차 처리 or 세미 병렬 처리 (동시 2개 제한)
    sem = asyncio.Semaphore(2)

    async def sem_task(doc):
        async with sem:
            if doc.get("image_urls"):  # 이미지가 있을 때
                await process_doc(doc)
            else:  # 이미지가 없을 때
                doc["ocr_text"] = ""
                doc["has_ocr"] = False
                doc["ocr_processed_at"] = datetime.now(timezone.utc)
                dst_col.insert_one(doc)
        
    await asyncio.gather(*(sem_task(doc) for doc in docs))

# 실행
if __name__ == "__main__":
    asyncio.run(main())