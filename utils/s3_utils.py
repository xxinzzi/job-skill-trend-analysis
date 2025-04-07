import boto3
import uuid
import os
import base64
from urllib.parse import urlparse
from io import BytesIO
import requests
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)
bucket_name = os.getenv("AWS_BUCKET_NAME")

def upload_image_to_s3(image_url: str, folder: str = "jobkorea_test") -> str:
    """
    이미지 URL 또는 data URI(base64)를 S3에 업로드하고 public URL 반환
    """
    try:
        if image_url.startswith("data:image/"):
            # Base64 data URI 처리
            header, encoded = image_url.split(",", 1)
            content_type = header.split(";")[0].split(":")[1]  # e.g. image/png
            ext = content_type.split("/")[1]
            image_data = base64.b64decode(encoded)
            filename = f"{folder}/{uuid.uuid4()}.{ext}"

            s3.upload_fileobj(
                Fileobj=BytesIO(image_data),
                Bucket=bucket_name,
                Key=filename,
                ExtraArgs={'ContentType': content_type}
            )
        else:
            # 일반 외부 이미지 URL 처리
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                "Referer": "https://www.jobkorea.co.kr/"
            }
            response = requests.get(image_url, headers=headers, timeout=5)
            response.raise_for_status()

            ext = os.path.splitext(urlparse(image_url).path)[1] or ".jpg"
            filename = f"{folder}/{uuid.uuid4()}{ext}"

            s3.upload_fileobj(
                Fileobj=BytesIO(response.content),
                Bucket=bucket_name,
                Key=filename,
                ExtraArgs={'ContentType': response.headers.get('Content-Type', 'image/jpeg')}
            )

        return f"https://{bucket_name}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{filename}"

    except Exception as e:
        print(f"❌ S3 업로드 실패: {e}")
        return None