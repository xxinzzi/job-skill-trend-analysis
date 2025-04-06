from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

# Mongo URI 환경변수에서 읽기
MONGO_URI = os.getenv("MONGO_URI")

# 전역 MongoClient 객체
client = None
db = None

def init_mongo():
    global client, db
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.server_info()  # 연결 테스트
        db = client["job-data"]
        return db
    except ConnectionFailure as e:
        print("❌ MongoDB 연결 실패:", e)
        return None

def get_collection(collection_name):
    """
    원하는 컬렉션 객체 반환
    """
    if db is None:
        print("❗ 먼저 init_mongo()를 호출해주세요.")
        return None
    return db[collection_name]