import sys
import os
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import random

# utils에서 MongoDB 및 S3 업로드 유틸 불러오기
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.mongo_utils import init_mongo, get_collection
from utils.s3_utils import upload_image_to_s3
from utils.captcha_utils import check_and_wait_for_captcha

# MongoDB 초기화 및 컬렉션 객체
init_mongo()
raw_col = get_collection("raw_postings_jobkorea_test")

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

    # 공고 수 추출
    match = re.search(r"\((\d+)\)", mid_cat_label)
    if match:
        total_count = int(match.group(1))
    else:
        total_count = 0

    # 페이지 수 계산
    total_pages = (total_count + 39) // 40
    mid_cat_clean_label = re.sub(r"\s*\(.*?\)", "", mid_cat_label).strip()

    start_page = int(input("총 페이지: {total_pages}\n시작할 페이지 번호를 입력하세요: "))

    # start_page로 이동
    if start_page > 1:
        for i in range(1, start_page):
            if i % 10 == 0:
                next_group_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btnPgnNext")))
                driver.execute_script("arguments[0].click();", next_group_btn)
            else:
                page_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f"a[data-page='{i+1}']")))
                driver.execute_script("arguments[0].click();", page_btn)
        time.sleep(1)

    current_page = start_page

    while current_page <= total_pages:
        print(f"\n⏳ {current_page}/{total_pages} 페이지 수집 중...")

        # 공고 리스트 수집
        dev_gi_list = wait.until(EC.presence_of_element_located((By.ID, "dev-gi-list")))
        postings = dev_gi_list.find_elements(By.CSS_SELECTOR, "tr.devloopArea")

        for post in postings:
            # CAPTCHA 감지 및 예외 처리
            check_and_wait_for_captcha(driver, current_page)

            title_elem = post.find_element(By.CSS_SELECTOR, "td.tplTit strong a")
            link = title_elem.get_attribute("href")

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

                title = company = ""

                # 공통 필드 먼저 구성
                document = {
                    "url": link,
                    "source": "jobkorea",
                    "job_category": "AI·개발·데이터",
                    "job_mid_category": mid_cat_clean_label,
                }

                # 구조1일 경우
                if structure1:
                    header_div = soup.select_one("h3.hd_3 > div.header")
                    company = header_div.select_one("span.coName").text.strip() if header_div and header_div.select_one("span.coName") else ""

                    title_tag = soup.select_one("h3.hd_3")
                    if title_tag:
                        for tag in title_tag.find_all(['div', 'span']):
                            tag.decompose()
                        title = title_tag.get_text(strip=True)

                    job_summary = soup.select_one("article.artReadJobSum div.tbRow.clear")
                    detail_section = soup.select_one("section#tab01.secReadDetail")
                    
                    document.update({
                        "title": title,
                        "company": company,
                        "jobsum_text": job_summary.get_text(separator="\n", strip=True) if job_summary else "",
                        "detail_text": detail_section.get_text(separator="\n", strip=True) if detail_section else ""
                    })

                    iframe_text = ""
                    image_urls = []

                    try:
                        iframe_elem = driver.find_element(By.CSS_SELECTOR, "iframe#gib_frame")
                        driver.switch_to.frame(iframe_elem)

                        # iframe 전체 HTML 파싱
                        iframe_soup = BeautifulSoup(driver.page_source, "html.parser")

                        # 텍스트 추출
                        content_div = iframe_soup.select_one("div.secDetailWrap")
                        if content_div:
                            iframe_text = content_div.get_text(separator="\n", strip=True)

                        # 이미지 추출
                        iframe_images = iframe_soup.find_all("img")
                        image_urls = [img.get("src") for img in iframe_images if img.get("src")]

                        driver.switch_to.default_content()

                    except Exception as iframe_err:
                        print("❌ iframe 처리 실패:", iframe_err)

                    if iframe_text:
                        document["iframe_text"] = iframe_text

                    if image_urls:
                        s3_urls = []
                        for url in image_urls:
                            s3_url = upload_image_to_s3(url, "jobkorea")
                            if s3_url:
                                s3_urls.append(s3_url)

                        if s3_urls:
                            document["image_urls"] = s3_urls
                        else:
                            # 업로드 실패 시 원본 URL fallback
                            s3_urls.append(url)

                # 구조2일 경우
                elif structure2:
                    title = soup.select_one("h2.title-recruit").text.strip() if soup.select_one("h2.title-recruit") else ""
                    company = soup.select_one("a.devTitleCoReadUrl").text.strip() if soup.select_one("a.devTitleCoReadUrl") else ""

                    section = soup.select_one("section.section-content")
                    aside = soup.select_one("section.aside")

                    document.update({
                        "title": title,
                        "company": company,
                        "section_text": section.get_text(separator="\n", strip=True) if section else "",
                        "aside_text": aside.get_text(separator="\n", strip=True) if aside else ""
                    })

                raw_col.insert_one(document)
                print("✅ 저장 완료:", title)

                driver.close()
                driver.switch_to.window(driver.window_handles[0])

            except Exception as post_err:
                print("❌ 공고 파싱 실패:", post_err)
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                continue
        
        # IP 차단 방지 속도 조절
        time.sleep(random.uniform(2, 5))

        # 다음 페이지 클릭
        current_page += 1
        if current_page > total_pages:
            break
        if current_page % 10 == 1:  # 11, 21, 31... → "다음" 버튼 눌러야 함
            try:
                next_group_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btnPgnNext")))
                driver.execute_script("arguments[0].click();", next_group_btn)
                time.sleep(2)
            except Exception as e:
                print("❌ 다음 버튼 클릭 실패:", e)
                break
        else:
            try:
                next_page_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f"a[data-page='{current_page}']")))
                driver.execute_script("arguments[0].click();", next_page_btn)
                time.sleep(2)
            except Exception as e:
                print(f"❌ {current_page} 페이지로 이동 실패:", e)
                break

except Exception as e:
    print(f"\n❌ 중단됨: {e}")
    print(f"중단된 페이지 번호: {current_page}")
    driver.quit()
    sys.exit(1)  # 강제 종료

driver.quit()