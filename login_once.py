import os
from playwright.sync_api import sync_playwright

def login():
    user_data_dir = os.path.join(os.getcwd(), "browser_data")
    with sync_playwright() as p:
        # Mở trình duyệt lên
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        page = browser.new_page()
        
        # Mở Gemini để bạn đăng nhập
        print(">>> Đang mở Gemini... Bạn hãy tiến hành đăng nhập nhé!")
        page.goto("https://gemini.google.com/")
        
        # Mở thêm một tab nữa cho Meta AI để đăng nhập luôn một thể
        page2 = browser.new_page()
        print(">>> Đang mở Meta AI... Đăng nhập luôn bên này nhé!")
        page2.goto("https://www.meta.ai/")
        
        print("\n[CHÚ Ý] Script sẽ giữ trình duyệt mở trong 3 PHÚT.")
        print("Hãy tranh thủ đăng nhập cả 2 trang. Sau khi xong, bạn chỉ cần TẮT trình duyệt đi là được.\n")
        
        # Đợi 3 phút (180.000 ms) để bạn thong thả thao tác
        page.wait_for_timeout(180000)
        browser.close()

if __name__ == '__main__':
    login()