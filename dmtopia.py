import time
import pickle
import requests
import pandas as pd
import re
from bs4 import BeautifulSoup
from selenium import webdriver as wb
from selenium.webdriver.common.by import By
import threading

# 전역 변수로 스레드만 남기고 GUI 관련 코드는 제거합니다.
update_status_event = threading.Event()
start_time = None

# 진행 상황을 표시할 함수 (터미널 출력용)
def update_status(message):
    elapsed_time = time.time() - start_time
    minutes, seconds = divmod(int(elapsed_time), 60)
    time_str = f"[{minutes:02}:{seconds:02}]"
    print(f"{time_str} {message}")

# 1. Selenium을 사용하여 로그인하고 쿠키 저장
def login_and_save_cookies():
    chrome_options = wb.ChromeOptions()
    chrome_options.add_argument('--headless')  # 헤드리스 모드
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    driver = wb.Chrome(options=chrome_options)
    update_status("Opened login page")
    driver.get("https://www.dometopia.com/member/login")

    driver.find_element(By.CSS_SELECTOR, '#userid').send_keys("koolca121922")
    driver.find_element(By.CSS_SELECTOR, '#password').send_keys("sjhs12jh19!@!(")
    driver.find_element(By.CSS_SELECTOR, '#doto_login > div.clearbox.mt20 > div.fleft > form > div > input.login-btn').click()
    update_status("Logged in")

    time.sleep(10)  # 페이지 로딩 대기

    cookies = driver.get_cookies()
    with open('cookies.pkl', 'wb') as f:
        pickle.dump(cookies, f)

    update_status("Cookies saved")
    driver.quit()

# 2. 쿠키 로드
def load_cookies(cookie_file):
    with open(cookie_file, 'rb') as f:
        return pickle.load(f)

# 3. 재고 현황 확인 및 추출
def check_stock_status(session, url):
    response = session.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    stock_text_elements = soup.find_all(string=re.compile(r'현재고:'))
    
    if stock_text_elements:
        return stock_text_elements[0]
    return None

# 4. 진행 중인 작업을 처리할 함수
def process_task():
    global start_time
    
    start_time = time.time()  # 작업 시작 시간 기록
    update_status("Starting process")
    login_and_save_cookies()

    cookies = load_cookies('cookies.pkl')
    session = requests.Session()
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain'), path=cookie.get('path'))

    excel_file = '도매토피아_누적데이터_test.xlsx'
    df = pd.read_excel(excel_file)
    id_values = df.iloc[:, 0].dropna().tolist()  # NaN 값을 제거하고 리스트로 변환

    if not id_values:
        update_status("엑셀 파일에서 ID를 찾을 수 없습니다.")
        return

    results = []

    for id_value in id_values:
        search_url = f"https://www.dometopia.com/goods/search?search_text={id_value}"
        try:
            response = session.get(search_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            link_elements = soup.select('a[href*="/goods/view?no="]')
            
            if link_elements:
                for link in link_elements:
                    href_value = link.get('href')
                    full_url = f"https://www.dometopia.com{href_value}"

                    stock_text = check_stock_status(session, full_url)
                    if stock_text:
                        match = re.search(r'현재고:\s*(\d+)', stock_text)
                        if match:
                            stock_quantity = match.group(1)
                            results.append({
                                '상품코드': f'JHSdmtopia_{id_value}', 
                                '원상품코드': f'{id_value}', 
                                '재고수량': stock_quantity
                            })
                            update_status(f"ID {id_value} - 재고수량: {stock_quantity}")
                        else:
                            results.append({
                                '상품코드': f'JHSdmtopia_{id_value}', 
                                '원상품코드': f'{id_value}', 
                                '재고수량': '수량 정보 없음'
                            })
                            update_status(f"ID {id_value} - Quantity information not available")
                    else:
                        results.append({
                            '상품코드': f'JHSdmtopia_{id_value}', 
                            '원상품코드': f'{id_value}', 
                            '재고수량': '재고 정보 없음'
                        })
                        update_status(f"ID {id_value} - Stock information not available")
                    break
            else:
                results.append({
                    '상품코드': f'JHSdmtopia_{id_value}', 
                    '원상품코드': f'{id_value}', 
                    '재고수량': '링크를 찾을 수 없음'
                })
                update_status(f"ID {id_value} - Link not found")
        except requests.RequestException as e:
            results.append({
                '상품코드': f'JHSdmtopia_{id_value}', 
                '원상품코드': f'{id_value}', 
                '재고수량': f'URL 요청 오류: {e}'
            })
            update_status(f"ID {id_value} - Request error: {e}")

    results_df = pd.DataFrame(results)
    results_df.to_excel('도매토피아_크롤링완료_.xlsx', index=False)  # xlsx 형식으로 저장
    update_status("Process completed")

# 5. 메인 함수
def main():
    process_task()

if __name__ == "__main__":
    main()
