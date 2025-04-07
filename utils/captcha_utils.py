from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

def check_and_wait_for_captcha(driver, current_page):
    try:
        # CAPTCHA가 포함될 수 있는 iframe 또는 div 감지
        captcha = driver.find_element(By.CSS_SELECTOR, "#recaptcha, .captcha_wrap, iframe[src*='captcha']")
        if captcha.is_displayed():
            print(f"\n🛑 CAPTCHA 감지됨! 현재 페이지: {current_page}")
            input("→ 보안문자 해결 후 [Enter] 키를 누르세요...")
    except NoSuchElementException:
        # 간혹 CAPTCHA가 iframe이 아니라 전체 페이지를 바꿈
        page_source = driver.page_source.lower()
        if "access denied" in page_source or "bot verification" in page_source or "captcha" in page_source:
            raise Exception(f"🚨 CAPTCHA 또는 IP 차단 페이지 감지됨 (페이지 {current_page})")