import sys
import os
import time
import uuid
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# utils에서 MongoDB 유틸 불러오기
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.mongo_utils import init_mongo, get_collection

# MongoDB 초기화 및 컬렉션 객체
init_mongo()
raw_col = get_collection("raw_postings")

# Selenium 크롬 드라이버 옵션
options = Options()
# options.add_argument("--headless")  # 필요 시 활성화
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 10)

# 잡코리아 채용 페이지 진입
driver.get("https://www.jobkorea.co.kr/recruit/joblist?menucode=duty")

# 대분류 선택 (AI·개발·데이터)
label = driver.find_element(By.CSS_SELECTOR, "label[for='duty_step1_10031']")
driver.execute_script("arguments[0].click();", label)

# 중분류 리스트
wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul#duty_step2_10031_ly li input[type='checkbox']")))
mid_categories = driver.find_elements(By.CSS_SELECTOR, "ul#duty_step2_10031_ly li input[type='checkbox']")

# 사용자로부터 중분류 선택
print(f"\n🔎 총 {len(mid_categories)}개의 중분류가 있습니다.")
for i, cat in enumerate(mid_categories):
    label = driver.find_element(By.CSS_SELECTOR, f"label[for='{cat.get_attribute('id')}']").text.strip()
    print(f"[{i}] {label}")
target_idx = int(input("\n🟡 수집할 중분류 인덱스 번호를 입력하세요: "))

# 선택된 중분류만 수집
try:
    mid_cat = mid_categories[target_idx]
    mid_cat_id = mid_cat.get_attribute("id")
    mid_cat_value = mid_cat.get_attribute("value")
    mid_cat_label = driver.find_element(By.CSS_SELECTOR, f"label[for='{mid_cat_id}']").text.strip()

    driver.execute_script("arguments[0].scrollIntoView(true);", mid_cat)
    time.sleep(0.5)
    driver.execute_script("arguments[0].click();", mid_cat)
    time.sleep(2)

    # 검색 버튼 클릭 후 로딩
    search_btn = wait.until(EC.element_to_be_clickable((By.ID, "dev-btn-search")))
    driver.execute_script("arguments[0].click();", search_btn)
    time.sleep(3)

    # 공고 수 추출: 'AI/ML 엔지니어 (418)' → 418
    match = re.search(r"\((\d+)\)", mid_cat_label)
    if match:
        total_count = int(match.group(1))
    else:
        total_count = 0

    # 페이지 수 계산
    total_pages = (total_count + 39) // 40
    mid_cat_clean_label = re.sub(r"\s*\(.*?\)", "", mid_cat_label).strip()

    print(f"\n총 {total_count}건 → {total_pages} 페이지에서 수집합니다.")

    for page in range(1, total_pages + 1):
        print(f"\n⏳ {page} 페이지 수집 중...")

        page_url = f"https://www.jobkorea.co.kr/recruit/joblist?menucode=duty&duty1=10031&duty2={mid_cat_value}&page={page}"
        driver.get(page_url)
        time.sleep(3)

        dev_gi_list = wait.until(EC.presence_of_element_located((By.ID, "dev-gi-list")))
        postings = dev_gi_list.find_elements(By.CSS_SELECTOR, "tr.devloopArea")

        for post in postings:
            try:
                title_elem = post.find_element(By.CSS_SELECTOR, "td.tplTit strong a")
                link = title_elem.get_attribute("href")

                # 상세 페이지 이동
                driver.execute_script("window.open(arguments[0]);", link)
                driver.switch_to.window(driver.window_handles[-1])
                time.sleep(2)

                soup = BeautifulSoup(driver.page_source, "html.parser")

                # 구조1 탐지
                structure1 = soup.select_one("div.tbCol.tbCoInfo") or soup.select_one("div.tbCol.tbCoResume")
                # 구조2 탐지
                structure2 = soup.select_one("div.dev-wrap-detailContents") or soup.select_one("div.recruit-data")

                raw_blocks = {}
                raw_text_blocks = {}
                title = company = ""

                # 구조1일 경우
                if structure1:
                    header_div = soup.select_one("h3.hd_3 > div.header")
                    company = header_div.select_one("span.coName").text.strip() if header_div and header_div.select_one("span.coName") else ""

                    title_tag = soup.select_one("h3.hd_3")
                    if title_tag:
                        for tag in title_tag.find_all(['div', 'span']):
                            tag.decompose()
                        title = title_tag.get_text(strip=True)

                    raw_blocks["corp_info_block"] = str(soup.select_one("div.tbCol.tbCoInfo"))
                    raw_blocks["requirements_block"] = str(soup.select_one("div.tbCol.tbCoResume"))

                    job_desc = soup.select_one("div.artRead_detail")
                    raw_blocks["job_description_block"] = {
                        "html": str(job_desc),
                        "image_urls": [img["src"] for img in job_desc.find_all("img") if img.get("src")]
                    } if job_desc else {}

                    raw_text_blocks["corp_info_text"] = soup.select_one("div.tbCol.tbCoInfo").get_text(strip=True) if soup.select_one("div.tbCol.tbCoInfo") else ""
                    raw_text_blocks["requirements_text"] = soup.select_one("div.tbCol.tbCoResume").get_text(strip=True) if soup.select_one("div.tbCol.tbCoResume") else ""
                    raw_text_blocks["job_description_text"] = job_desc.get_text(strip=True) if job_desc else ""

                # 구조2일 경우
                elif structure2:
                    title = soup.select_one("h2.title-recruit").text.strip() if soup.select_one("h2.title-recruit") else ""
                    company = soup.select_one("a.devTitleCoReadUrl").text.strip() if soup.select_one("a.devTitleCoReadUrl") else ""

                    raw_blocks["corp_info_block"] = str(soup.select_one("article.devCompanyInfo"))
                    raw_blocks["requirements_block"] = str(soup.select_one("div.recruit-data"))

                    job_desc = soup.select_one("div.dev-wrap-detailContents")
                    raw_blocks["job_description_block"] = {
                        "html": str(job_desc),
                        "image_urls": [img["src"] for img in job_desc.find_all("img") if img.get("src")]
                    } if job_desc else {}

                    raw_text_blocks["corp_info_text"] = soup.select_one("article.devCompanyInfo").get_text(strip=True) if soup.select_one("article.devCompanyInfo") else ""
                    raw_text_blocks["requirements_text"] = soup.select_one("div.recruit-data").get_text(strip=True) if soup.select_one("div.recruit-data") else ""
                    raw_text_blocks["job_description_text"] = job_desc.get_text(strip=True) if job_desc else ""

                document = {
                    "url": link,
                    "source": "jobkorea",
                    "title": title,
                    "company": company,
                    "job_category": mid_cat_clean_label,
                    "raw_html_blocks": raw_blocks,
                    "raw_text_blocks": raw_text_blocks,
                    "crawl_id": str(uuid.uuid4()),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                raw_col.insert_one(document)
                print("✅ 저장 완료:", title)

                driver.close()
                driver.switch_to.window(driver.window_handles[0])

            except Exception as post_err:
                print("❌ 공고 파싱 실패:", post_err)
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                continue

except Exception as e:
    print("❌ 중분류 처리 실패:", e)

driver.quit()