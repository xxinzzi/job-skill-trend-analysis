from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time

# 셀레니움 드라이버 설정
options = Options()
options.add_argument("--headless")  # GUI 없이 실행할 경우 주석 해제
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=options)
actions = ActionChains(driver)
wait = WebDriverWait(driver, 10)

# 결과 저장 리스트
results = []

# 잡코리아 직무별 채용공고 검색 페이지 접속
driver.get("https://www.jobkorea.co.kr/recruit/joblist?menucode=duty")
time.sleep(3)

# 대분류 'AI·개발·데이터' 선택
label = driver.find_element(By.CSS_SELECTOR, "label[for='duty_step1_10031']")
driver.execute_script("arguments[0].click();", label)
time.sleep(2)
print("✅ 대분류 'AI·개발·데이터' 선택 완료")

# 중분류 직무 리스트 수집
wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul#duty_step2_10031_ly li input[type='checkbox']")))
mid_categories = driver.find_elements(By.CSS_SELECTOR, "ul#duty_step2_10031_ly li input[type='checkbox']")
print("✅ 중분류 직무 리스트 수집 완료: ", len(mid_categories))

# 중분류 루프 시작
for idx in range(len(mid_categories)):
    try:
        # 중분류 요소 재선언 (stale 방지)
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul#duty_step2_10031_ly li input[type='checkbox']")))
        mid_categories = driver.find_elements(By.CSS_SELECTOR, "ul#duty_step2_10031_ly li input[type='checkbox']")
        mid_cat = mid_categories[idx]

        mid_cat_id = mid_cat.get_attribute("id")
        mid_cat_label = driver.find_element(By.CSS_SELECTOR, f"label[for='{mid_cat_id}']").text.strip()

        print(f"\n➡️ [{idx+1}/{len(mid_categories)}] {mid_cat_label} 선택 중...")

        # 스크롤 후 강제 클릭
        driver.execute_script("arguments[0].scrollIntoView(true);", mid_cat)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", mid_cat)
        time.sleep(2)

        # "선택된 조건 검색하기" 버튼 클릭
        search_btn = wait.until(EC.element_to_be_clickable((By.ID, "dev-btn-search")))
        driver.execute_script("arguments[0].click();", search_btn)
        time.sleep(3)
        print(f"✅ [{mid_cat_label}] 검색 시작")

        # 스크롤 다운
        driver.execute_script("window.scrollBy(0, 2200);")
        time.sleep(2)

        page_num = 1
        while True:
            try:
                dev_gi_list = driver.find_element(By.ID, "dev-gi-list")
                postings = dev_gi_list.find_elements(By.CSS_SELECTOR, "tr.devloopArea")

                if not postings:
                    print(f"⚠️ {page_num}페이지 - 채용공고 없음")
                    break

                print(f"✅ {page_num}페이지 - 채용공고 {len(postings)}개 수집 시도")

                for post in postings:
                    try:
                        title_elem = post.find_element(By.CSS_SELECTOR, "td.tplTit strong a")
                        company_elem = post.find_element(By.CSS_SELECTOR, "td.tplCo a")
                        title = title_elem.get_attribute("title").strip()
                        company = company_elem.text.strip()
                        link = title_elem.get_attribute("href")

                        # 기타 정보
                        etc_cells = post.find_elements(By.CSS_SELECTOR, "td.tplTit p.etc span.cell")
                        experience = etc_cells[0].text if len(etc_cells) > 0 else ""
                        education = etc_cells[1].text if len(etc_cells) > 1 else ""
                        employment = etc_cells[2].text if len(etc_cells) > 2 else ""

                        # 기술 키워드
                        skills = post.find_element(By.CSS_SELECTOR, "td.tplTit p.dsc").text.strip() if post.find_elements(By.CSS_SELECTOR, "td.tplTit p.dsc") else ""

                        results.append({
                            "직무(대분류)": "AI·개발·데이터",
                            "직무(중분류)": mid_cat_label,
                            "회사명": company,
                            "공고제목": title,
                            "경력": experience,
                            "학력": education,
                            "고용형태": employment,
                            "기술키워드": skills,
                            "공고링크": link
                        })

                    except Exception as post_err:
                        print("⚠️ 개별 공고 파싱 실패:", post_err)
                        continue
                
                # 다음 페이지 이동
                try:
                    next_btn = driver.find_element(By.CSS_SELECTOR, "a.btnPgnNext")
                    if "disabled" in next_btn.get_attribute("class"):
                        print(f"⛔ 마지막 페이지 도달 ({page_num}페이지)")
                        break
                    driver.execute_script("arguments[0].click();", next_btn)
                    time.sleep(2)
                    page_num += 1
                except:
                    print(f"⛔ 마지막 페이지 도달 ({page_num}페이지)")
                    break

            except Exception as page_err:
                print(f"❌ 공고 로딩 실패 (페이지 {page_num}): {page_err}")
                break
        
        # 다음 중분류를 위해 초기화
        print(f"🔁 [{mid_cat_label}] 완료. 초기화 중...")
        driver.get("https://www.jobkorea.co.kr/recruit/joblist?menucode=duty")
        time.sleep(3)
        driver.execute_script("document.querySelector(\"label[for='duty_step1_10031']\").click();")
        time.sleep(2)

    except Exception as e:
        print(f"❌ 중분류 [{idx+1}] 처리 오류: {e}")
        continue

# 드라이버 종료 
driver.quit()

# 결과 저장
df = pd.DataFrame(results)
df.to_csv("jobkorea_ai_dev_all_filtered.csv", index=False, encoding="utf-8-sig")
print(f"\n✅ 크롤링 완료. 총 {len(results)}건 저장됨 → jobkorea_ai_dev_all_filtered.csv")
