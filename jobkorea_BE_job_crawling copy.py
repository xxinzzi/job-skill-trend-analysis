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
# options.add_argument("--headless")  # GUI 없이 실행할 경우 주석 해제
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=options)
actions = ActionChains(driver)
wait = WebDriverWait(driver, 10)

# 결과 저장 리스트
results = []

# 잡코리아 직무별 채용공고 검색 페이지 접속
driver.get("https://www.jobkorea.co.kr/recruit/joblist?menucode=duty")

# 대분류 'AI·개발·데이터' 선택
label = driver.find_element(By.CSS_SELECTOR, "label[for='duty_step1_10031']")
driver.execute_script("arguments[0].click();", label)
print("✅ 대분류 'AI·개발·데이터' 선택 완료")

# 중분류 직무 리스트 수집
wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul#duty_step2_10031_ly li input[type='checkbox']")))
mid_categories = driver.find_elements(By.CSS_SELECTOR, "ul#duty_step2_10031_ly li input[type='checkbox']")
print("✅ 중분류 직무 리스트 수집 완료: ", len(mid_categories))

# ✅ 중분류 첫 번째 항목만 처리
for idx in range(1):
    try:
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul#duty_step2_10031_ly li input[type='checkbox']")))
        mid_categories = driver.find_elements(By.CSS_SELECTOR, "ul#duty_step2_10031_ly li input[type='checkbox']")
        mid_cat = mid_categories[idx]

        mid_cat_id = mid_cat.get_attribute("id")
        mid_cat_label = driver.find_element(By.CSS_SELECTOR, f"label[for='{mid_cat_id}']").text.strip()

        print(f"\n➡️ [테스트] {mid_cat_label} 선택 중...")

        driver.execute_script("arguments[0].scrollIntoView(true);", mid_cat)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", mid_cat)
        time.sleep(2)

        search_btn = wait.until(EC.element_to_be_clickable((By.ID, "dev-btn-search")))
        driver.execute_script("arguments[0].click();", search_btn)
        time.sleep(3)
        print(f"✅ [{mid_cat_label}] 검색 시작")

        # ✅ 첫 페이지만 수집
        page_num = 1
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

                    etc_cells = post.find_elements(By.CSS_SELECTOR, "td.tplTit p.etc span.cell")
                    experience = etc_cells[0].text if len(etc_cells) > 0 else ""
                    education = etc_cells[1].text if len(etc_cells) > 1 else ""
                    employment = etc_cells[2].text if len(etc_cells) > 2 else ""
                    skills = post.find_element(By.CSS_SELECTOR, "td.tplTit p.dsc").text.strip() if post.find_elements(By.CSS_SELECTOR, "td.tplTit p.dsc") else ""

                    # 상세페이지에서 기업형태 가져오기
                    driver.execute_script("window.open(arguments[0]);", link)
                    driver.switch_to.window(driver.window_handles[-1])
                    time.sleep(2)

                    corp_type = ""

                    try:
                        # 공고 구조 1 시도
                        info_block = driver.find_element(By.CSS_SELECTOR, "div.tbCol.tbCoInfo")
                        print("✅ 공고 구조 1 감지됨")

                        tb_list = info_block.find_element(By.CSS_SELECTOR, "dl.tbList")
                        children = tb_list.find_elements(By.XPATH, "./*")  # dt, dd 모두 포함

                        for i in range(len(children)):                        
                            if children[i].tag_name == "dt" and "기업형태" in children[i].text.strip().replace("\n", "").replace(" ", ""):
                                if i + 1 < len(children) and children[i + 1].tag_name == "dd":                                 
                                    corp_type = children[i + 1].text.strip()  
                                    print("✅ 기업형태 수집 완료")                               
                                break

                    except:
                        # 공고 구조 2 처리
                        print("✅ 공고 구조 2 감지됨")
                        try:
                            info_items = driver.find_elements(By.CSS_SELECTOR, "div.information-item.information-corp-type")

                            for item in info_items:
                                try:
                                    title_elem = item.find_element(By.CSS_SELECTOR, "p.information-title")
                                    if "기업구분" in title_elem.text:
                                        subtitle_elem = item.find_element(By.CSS_SELECTOR, "p.information-subtitle")
                                        corp_type = subtitle_elem.text.strip()
                                        print("✅ 기업형태 수집 완료 (구조 2):", corp_type)
                                        break
                                except:
                                    continue
                        except Exception as structure2_err:
                            print("❌ 구조 2 수집 실패:", structure2_err)

                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])

                    results.append({
                        "직무(대분류)": "AI·개발·데이터",
                        "직무(중분류)": mid_cat_label,
                        "회사명": company,
                        "공고제목": title,
                        "경력": experience,
                        "학력": education,
                        "지역": employment,
                        "기술키워드": skills,
                        "기업형태": corp_type,
                        "공고링크": link
                    })

                except Exception as post_err:
                    print("❌ 개별 공고 파싱 실패:", post_err)
                    continue

        except Exception as page_err:
            print(f"❌ 공고 로딩 실패 (페이지 {page_num}): {page_err}")
            continue

    except Exception as e:
        print(f"❌ 테스트 직무 처리 오류: {e}")
        continue

# 드라이버 종료 및 결과 저장
driver.quit()
df = pd.DataFrame(results)
df.to_csv("jobkorea_test_page1.csv", index=False, encoding="utf-8-sig")
print(f"\n✅ 테스트 완료. 총 {len(results)}건 저장됨 → jobkorea_test_page1.csv")