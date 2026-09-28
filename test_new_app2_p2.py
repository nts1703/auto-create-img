import os
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# ==================== CONFIG ====================
app.config['ANH_MAU_FOLDER'] = 'anh_mau'
app.config['DANHSACH_ANH_FOLDER'] = 'danhsach_anh'
app.config['KETQUA_FOLDER'] = 'ketqua'

folders = [
    app.config['ANH_MAU_FOLDER'],
    app.config['DANHSACH_ANH_FOLDER'],
    app.config['KETQUA_FOLDER']
]
for folder in folders:
    os.makedirs(folder, exist_ok=True)

PROFILES = [f"browser_data_{i}" for i in range(1, 9)]

# ===============================================
PROMPT_PHAN_TICH_Ao = "Hãy phân tích chi tiết chiếc áo trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ. Phân biệt rõ đâu là mặt trước và sau chiếc áo"
PROMPT_PHAN_TICH_VAY = "Hãy phân tích chi tiết chiếc váy trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."
PROMPT_PHAN_TICH_QUAN = "Hãy phân tích chi tiết chiếc quần trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."
PROMPT_PHAN_TICH_CA_SET = "Hãy phân tích chi tiết cả set trang phục trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."
PROMPT_PHAN_TICH_CHAN_VAY = "Hãy phân tích chi tiết chân váy trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."

PROMPT_CHINH_SUA_DAU = "Hãy chỉnh sửa ảnh này để người trong ảnh mặc đúng bộ đồ mà bạn vừa phân tích ở tin nhắn trước. Giữ nguyên tư thế, gương mặt, ánh sáng, background và chất lượng ảnh gốc. Chỉ thay đổi trang phục. độ nét 4k"
PROMPT_TUONG_TU = "Hãy chỉnh sửa ảnh này để người trong ảnh mặc đúng bộ đồ mà bạn vừa phân tích ở tin nhắn trước. Giữ nguyên tư thế, gương mặt, ánh sáng, background và chất lượng ảnh gốc. Chỉ thay đổi trang phục. độ nét 4k"

# Nhận biết GPT đã sinh xong ảnh
RESULT_SELECTOR = (
    'button[aria-label*="Chia sẻ hình ảnh"], '
    'button[aria-label*="Share this image"], '
    'button[aria-label*="Chia sẻ"], '
    'button[aria-label*="Share"]'
)

LIMIT_TEXTS = [
    "Bạn đã hết lượt tạo hình ảnh",
    "Bạn đã đạt giới hạn yêu cầu tạo ảnh của gói Free. Bạn có thể tạo thêm hình ảnh sau khi giới hạn được đặt lại sau 24 giờ.",
    "hết lượt tạo ảnh",
    "đã chạm giới hạn sử dụng của gói Free",
    "You've reached your limit",
    "Bạn đã đạt giới hạn yêu cầu tạo ảnh của gói Free."
]


def get_today_output_folder(base_folder='ketqua'):
    """Tạo thư mục lưu ảnh theo ngày hiện tại: ketqua/YYYY-MM-DD/"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    folder_path = os.path.join(base_folder, today_str)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


def download_latest_generated_image(page, output_dir, image_index):
    try:
        # 1. Định vị tin nhắn Assistant cuối cùng
        last_assistant_turn = page.locator('article, div[data-message-author-role="assistant"]').last
        if not last_assistant_turn.is_visible():
            return False

        # 2. Rê chuột vào ảnh cuối cùng để kích hoạt nút Share (tránh trường hợp bị ẩn)
        img_el = last_assistant_turn.locator('img[alt*="Generated image"], img[alt*="Hình ảnh được tạo"]').last
        if img_el.is_visible():
            img_el.hover()
            page.wait_for_timeout(300)

        # 3. Tìm nút Chia sẻ chuẩn
        share_btn = last_assistant_turn.locator(RESULT_SELECTOR).last

        if share_btn.is_visible():
            print(f"   📤 Đã tìm thấy icon Chia sẻ, đang click...")
            share_btn.click(force=True)
            page.wait_for_timeout(800)  # Chờ menu xuất hiện

            # 4. Bấm nút Tải xuống trong menu
            download_btn = page.locator(
                'button:has-text("Tải xuống"), button:has-text("Download"), '
                'div[role="menuitem"]:has-text("Tải xuống"), div[role="menuitem"]:has-text("Download")'
            ).last

            if download_btn.is_visible():
                print(f"   📥 Đã thấy nút Tải xuống! Đang tải file...")
                timestamp = datetime.now().strftime("%H%M%S")
                file_name = f"result_img_{image_index}_{timestamp}.png"
                save_path = os.path.join(output_dir, file_name)

                with page.expect_download(timeout=15000) as download_info:
                    download_btn.click(force=True)

                download = download_info.value
                download.save_as(save_path)
                print(f"   💾✅ Đã lưu ảnh thành công: {save_path}")

                page.wait_for_timeout(500)
                try:
                    page.keyboard.press("Escape")
                except Exception:
                    pass

                return True
            else:
                print("   ⚠️ Không thấy nút Tải xuống trong menu.")
                page.keyboard.press("Escape")

    except Exception as e:
        print(f"   ⚠️ Lỗi trong quá trình tải ảnh: {e}")
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

    return False


def is_limit_reached(page):
    """Kiểm tra thông báo hết lượt trên khung thông báo lỗi hoặc tin nhắn mới nhất"""
    try:
        alert_selectors = [
            '[role="alert"]',
            '.text-token-text-error',
            'div[class*="bg-red"]',
            'div[class*="border-red"]'
        ]
        for sel in alert_selectors:
            elements = page.locator(sel)
            for i in range(elements.count()):
                if elements.nth(i).is_visible():
                    txt = elements.nth(i).inner_text().lower()
                    if any(limit_txt.lower() in txt for limit_txt in LIMIT_TEXTS):
                        return True

        last_turn = page.locator('article, div[data-message-author-role="assistant"]').last
        if last_turn.is_visible():
            last_text = last_turn.inner_text().lower()
            if any(limit_txt.lower() in last_text for limit_txt in LIMIT_TEXTS):
                return True

        return False
    except Exception:
        return False


def dismiss_popups(page):
    """Tự động đóng popup"""
    close_selectors = [
        'button[data-testid="close-button"]',
        'button[aria-label="Đóng"]',
        'button[aria-label="Close"]',
        'button[aria-label*="Đóng"]',
        'button[aria-label*="Close"]',
        'button:has-text("Đóng")',
        'button:has-text("Close")',
        '[data-testid="modal-close"]',
        'button.absolute.right-4.top-4',
    ]
    for sel in close_selectors:
        try:
            btns = page.locator(sel)
            count = btns.count()
            for i in range(count):
                btn = btns.nth(i)
                if btn.is_visible():
                    btn.click(force=True, timeout=2000)
                    print(f"   ✖️ Đã đóng popup bằng: {sel}")
                    page.wait_for_timeout(600)
                    return True
        except Exception:
            continue
    return False


def wait_for_text_generation(page, step_name=""):
    print(f"   ⏳ Đang chờ GPT xử lý {step_name}...")
    stop_btn_selector = 'button[aria-label*="Stop"], button[aria-label*="Dừng"]'
    try:
        page.wait_for_selector(stop_btn_selector, timeout=10000)
    except Exception:
        pass
    try:
        page.wait_for_selector(stop_btn_selector, state="detached", timeout=180000)
        print(f"   ✅ Hoàn thành {step_name}")
        page.wait_for_timeout(2000)
    except Exception:
        print(f"   ⚠️ GPT có thể bị kẹt. Đang ép dừng...")
        try:
            page.locator(stop_btn_selector).first.click(timeout=5000)
            page.wait_for_timeout(2000)
        except Exception:
            pass


def upload_image(page, image_path, is_first=False):
    filename = os.path.basename(image_path)
    print(f"   📸 Đang attach ảnh: {filename}")

    try:
        page.locator('#prompt-textarea').click(force=True, timeout=5000)
        page.wait_for_timeout(400)
        page.locator('#upload-files').set_input_files(image_path, timeout=8000)
        page.wait_for_selector(
            'button[aria-label*="Remove"], button[aria-label*="Xóa tệp"]', timeout=12000
        )
        print(f"   ✅ Đã attach xong (cách cũ): {filename}")
        page.wait_for_timeout(1500)
        return True
    except Exception as e:
        print(f"   ⚠️ Cách cũ thất bại: {e}")

    try:
        print("   🔄 Chuyển sang cách upload mới...")
        plus_btn = page.locator('button[aria-label="Thêm tệp và nội dung khác"]').first
        plus_btn.wait_for(state="visible", timeout=8000)
        plus_btn.click()
        page.wait_for_timeout(600)
        with page.expect_file_chooser(timeout=12000) as fc_info:
            menu_item = page.locator('button:has-text("Thêm ảnh & tệp")').first
            menu_item.wait_for(state="visible", timeout=6000)
            menu_item.click()
            file_chooser = fc_info.value
            file_chooser.set_files(image_path)
        page.wait_for_selector(
            'button[aria-label*="Remove"], button[aria-label*="Xóa"], '
            '[data-testid*="file-thumbnail"], [data-testid*="attachment"]', timeout=10000
        )
        print(f"   ✅ Đã attach xong (cách mới): {filename}")
        page.wait_for_timeout(1500)
        return True
    except Exception as e:
        print(f"   ❌ Lỗi attach {filename}: {e}")
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return False


def send_prompt(page, text):
    try:
        composer = page.locator('#prompt-textarea').first
        composer.click(force=True, timeout=5000)
        page.wait_for_timeout(400)
        composer.fill(text)
        page.wait_for_timeout(600)
        send_button = page.locator(
            'button[data-testid="send-button"], #composer-submit-button, button[aria-label*="Gửi lời nhắc"]'
        ).first
        send_button.wait_for(state="visible", timeout=8000)
        send_button.click()
        print(f"   📤 Đã gửi prompt (cách cũ)")
        return
    except Exception as e:
        print(f"   ⚠️ Cách gửi cũ thất bại: {e}")

    try:
        print("   🔄 Chuyển sang cách gửi mới...")
        composer = page.locator(
            'div.ProseMirror[contenteditable="true"], '
            'div[contenteditable="true"][role="textbox"], '
            '[data-composer-markdown][contenteditable="true"]'
        ).first
        composer.wait_for(state="visible", timeout=10000)
        composer.click(force=True)
        page.wait_for_timeout(300)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.wait_for_timeout(200)
        page.keyboard.type(text, delay=8)
        page.wait_for_timeout(500)
        send_button = page.locator(
            'button[type="submit"]:not([disabled]), '
            'button[aria-label*="Gửi"], button[aria-label*="Send"]'
        ).first
        send_button.wait_for(state="visible", timeout=8000)
        send_button.click()
        print(f"   📤 Đã gửi prompt (cách mới)")
    except Exception as e:
        print(f"   ⚠️ Lỗi gửi prompt: {e}")
        try:
            page.keyboard.press("Enter")
        except Exception:
            pass


def open_browser(playwright, profile_path):
    print(f"🌐 Mở profile: {profile_path}")
    browser = playwright.chromium.launch_persistent_context(
        user_data_dir=profile_path,
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.goto("https://chatgpt.com/")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(7)
    dismiss_popups(page)
    return browser, page


def run_chatgpt_automation(anh_mau_path, list_anh_paths, prompt_phan_tich):
    total_images = len(list_anh_paths)
    current_idx = 0
    profile_idx = 0

    today_folder = get_today_output_folder(app.config['KETQUA_FOLDER'])

    with sync_playwright() as p:
        while current_idx < total_images and profile_idx < len(PROFILES):
            profile_path = PROFILES[profile_idx]
            browser, page = open_browser(p, profile_path)

            try:
                print(f"\n=== PROFILE {profile_idx + 1} | Gửi lại Ảnh mẫu ===")
                dismiss_popups(page)
                if not upload_image(page, anh_mau_path, is_first=True):
                    print("❌ Không upload được ảnh mẫu → chuyển profile")
                    browser.close()
                    profile_idx += 1
                    continue

                send_prompt(page, prompt_phan_tich)
                wait_for_text_generation(page, "Ảnh mẫu")
                dismiss_popups(page)

                while current_idx < total_images:
                    anh_path = list_anh_paths[current_idx]
                    print(f"\n=== PROFILE {profile_idx + 1} | Ảnh {current_idx + 1}/{total_images} ===")
                    dismiss_popups(page)

                    current_results_count = page.locator(RESULT_SELECTOR).count()

                    if not upload_image(page, anh_path):
                        print(f"   ⚠️ Upload ảnh {current_idx + 1} thất bại → bỏ qua")
                        current_idx += 1
                        continue

                    prompt = PROMPT_CHINH_SUA_DAU if current_idx == 0 else PROMPT_TUONG_TU
                    send_prompt(page, prompt)

                    print(f"   ⏳ Đang chờ GPT vẽ ảnh (tối đa 3 phút)...")
                    start_time = time.time()
                    timeout_seconds = 180
                    check_interval = 3
                    switched_due_to_limit = False

                    # Hoãn 10 giây ban đầu để GPT kịp xuất hiện phản hồi mới
                    page.wait_for_timeout(10000)

                    while time.time() - start_time < timeout_seconds:
                        try:
                            new_count = page.locator(RESULT_SELECTOR).count()
                            if new_count > current_results_count:
                                if download_latest_generated_image(page, today_folder, current_idx + 1):
                                    current_idx += 1
                                    dismiss_popups(page)
                                    break
                        except Exception:
                            pass

                        if is_limit_reached(page):
                            print(f"\n🚫 PHÁT HIỆN HẾT LƯỢT ở Profile {profile_idx + 1}")
                            print(f"   → Đã hoàn thành {current_idx}/{total_images} ảnh")
                            print(f"   → Chờ 3 giây rồi chuyển sang Profile {profile_idx + 2}...")
                            page.wait_for_timeout(3000)
                            switched_due_to_limit = True
                            break

                        page.wait_for_timeout(check_interval * 1000)
                    else:
                        print(f"   ⚠️ Timeout 3 phút → bỏ qua ảnh này")
                        current_idx += 1
                        try:
                            page.locator('button[aria-label*="Stop"], button[aria-label*="Dừng"]').first.click(timeout=3000)
                            page.wait_for_timeout(1500)
                        except Exception:
                            pass

                    if switched_due_to_limit:
                        break

            finally:
                try:
                    browser.close()
                except Exception:
                    pass

            if current_idx < total_images:
                profile_idx += 1
            else:
                break

    if current_idx >= total_images:
        print("\n🎉 HOÀN THÀNH TOÀN BỘ ẢNH!")
    else:
        print(f"\n⚠️ Đã dùng hết 8 profile. Mới xong {current_idx}/{total_images} ảnh.")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process', methods=['POST'])
def process():
    try:
        anh_mau = request.files.get('anh_mau')
        if not anh_mau or not anh_mau.filename:
            return "Chưa chọn ảnh mẫu", 400
        anh_mau_path = os.path.join(app.config['ANH_MAU_FOLDER'], anh_mau.filename)
        anh_mau.save(anh_mau_path)

        files = request.files.getlist('danhsach_anh')
        list_anh_paths = []
        for file in files:
            if file.filename:
                path = os.path.join(app.config['DANHSACH_ANH_FOLDER'], file.filename)
                file.save(path)
                list_anh_paths.append(path)

        if not list_anh_paths:
            return "Chưa chọn ảnh nào cần chỉnh", 400

        loai_sp = request.form.get('loai_sp', 'ao')
        prompt_map = {
            'ao': PROMPT_PHAN_TICH_Ao,
            'vay': PROMPT_PHAN_TICH_VAY,
            'quan': PROMPT_PHAN_TICH_QUAN,
            'ca_set': PROMPT_PHAN_TICH_CA_SET,
            'chan_vay': PROMPT_PHAN_TICH_CHAN_VAY
        }
        prompt_phan_tich = prompt_map.get(loai_sp, PROMPT_PHAN_TICH_Ao)

        print(f"📌 Loại sản phẩm đã chọn: {loai_sp}")
        print(f"📌 Prompt phân tích sẽ dùng: {prompt_phan_tich[:80]}...")

        thread = threading.Thread(
            target=run_chatgpt_automation,
            args=(anh_mau_path, list_anh_paths, prompt_phan_tich)
        )
        thread.start()

        return "Tool đang chạy ngầm! Hãy mở Terminal để xem tiến trình."
    except Exception as e:
        return f"Lỗi: {str(e)}", 500


if __name__ == '__main__':
    app.run(debug=True)
    