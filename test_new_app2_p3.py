import os
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
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

# ===== Trạng thái tiến trình =====
progress_lock = threading.Lock()
progress = {
    "running": False,
    "status": "idle",
    "message": "",
    "current": 0,
    "total": 0,
    "profile": 0,
    "images": []
}


def update_progress(**kwargs):
    with progress_lock:
        progress.update(kwargs)


def add_progress_image(rel_path):
    with progress_lock:
        if rel_path not in progress["images"]:
            progress["images"].append(rel_path)
        progress["current"] = len(progress["images"])


# ===============================================
PROMPT_PHAN_TICH_Ao = "Hãy phân tích chi tiết chiếc áo trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ. Phân biệt rõ đâu là mặt trước và sau chiếc áo"
PROMPT_PHAN_TICH_VAY = "Hãy phân tích chi tiết chiếc váy trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."
PROMPT_PHAN_TICH_QUAN = "Hãy phân tích chi tiết chiếc quần trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."
PROMPT_PHAN_TICH_CA_SET = "Hãy phân tích chi tiết cả set trang phục trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."
PROMPT_PHAN_TICH_CHAN_VAY = "Hãy phân tích chi tiết chân váy trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."

PROMPT_CHINH_SUA_DAU = "Hãy chỉnh sửa ảnh này để người trong ảnh mặc đúng bộ đồ mà bạn vừa phân tích ở tin nhắn trước. Giữ nguyên tư thế, gương mặt, ánh sáng, background và chất lượng ảnh gốc. Chỉ thay đổi trang phục. độ nét 4k"
PROMPT_TUONG_TU = "Hãy chỉnh sửa ảnh này để người trong ảnh mặc đúng bộ đồ mà bạn vừa phân tích ở tin nhắn trước. Giữ nguyên tư thế, gương mặt, ánh sáng, background và chất lượng ảnh gốc. Chỉ thay đổi trang phục. độ nét 4k"

SHARE_ON_IMAGE = (
    'button[aria-label="Chia sẻ hình ảnh này"], '
    'button[aria-label*="Chia sẻ hình ảnh"], '
    'button[aria-label*="Chia sẻ ảnh"], '
    'button[aria-label*="Chia sẻ ảnh đã tạo"], '
    'button[aria-label*="Share this image"], '
    'button[aria-label*="Share generated"], '
    'button[aria-label*="Share image"]'
)
DOWNLOAD_IN_MENU = (
    'button.interactive-button:has-text("Tải xuống"), '
    'button:has-text("Tải xuống"), '
    'button:has-text("Download"), '
    'div[role="menuitem"]:has-text("Tải xuống")'
)
LIMIT_TEXTS = [
    "Bạn đã hết lượt tạo hình ảnh",
    "Bạn đã đạt giới hạn yêu cầu tạo ảnh của gói Free. Bạn có thể tạo thêm hình ảnh sau khi giới hạn được đặt lại sau 24 giờ.",
    "hết lượt tạo ảnh",
    "đã chạm giới hạn sử dụng của gói Free",
    "You've reached your limit",
    "Bạn đã đạt giới hạn yêu cầu tạo ảnh của gói Free."
]

STOP_BTN_SELECTOR = 'button[aria-label*="Stop"], button[aria-label*="Dừng"], button[aria-label*="Tạm dừng"]'

ATTACH_CHIP_SELECTOR = (
    'button[aria-label*="Remove"], button[aria-label*="Xóa"], '
    'button[aria-label*="Remove file"], button[aria-label*="Xóa tệp"], '
    '[data-testid*="file-thumbnail"], [data-testid*="attachment"], '
    '[data-testid*="file"], form img, [class*="thumbnail"] img, '
    '[class*="attachment"] img, div[role="button"] img'
)


def get_today_output_folder(base_folder='ketqua'):
    today_str = datetime.now().strftime("%Y-%m-%d")
    folder_path = os.path.join(base_folder, today_str)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path, today_str


def get_attach_count(page):
    try:
        return page.locator(ATTACH_CHIP_SELECTOR).count()
    except Exception:
        return 0


def get_share_count(page):
    try:
        return page.locator(SHARE_ON_IMAGE).count()
    except Exception:
        return 0


def download_latest_generated_image(page, output_dir, today_str, image_index):
    try:
        share_btn = page.locator(SHARE_ON_IMAGE).last
        if not share_btn.is_visible(timeout=5000):
            print("   ⚠️ Không tìm thấy nút Share trên ảnh")
            return None

        print("   📤 Đã thấy nút Share trên ảnh, đang click...")
        share_btn.click(force=True)
        page.wait_for_timeout(1500)

        download_btn = page.locator(DOWNLOAD_IN_MENU).last
        if not download_btn.is_visible(timeout=6000):
            print("   ⚠️ Không thấy nút Tải xuống trong menu")
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            return None

        print("   📥 Đang click Tải xuống...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"anh_tao_{image_index:02d}_{timestamp}.png"
        save_path = os.path.join(output_dir, file_name)

        with page.expect_download(timeout=15000) as download_info:
            download_btn.evaluate("el => el.click()")

        download = download_info.value
        download.save_as(save_path)
        print(f"   💾✅ ĐÃ LƯU: {save_path}")

        page.wait_for_timeout(500)
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

        return f"{today_str}/{file_name}"

    except Exception as e:
        print(f"   ⚠️ Lỗi tải ảnh: {e}")
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return None


def is_limit_reached(page):
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
            for i in range(btns.count()):
                btn = btns.nth(i)
                if btn.is_visible():
                    btn.click(force=True, timeout=2000)
                    print(f"   ✖️ Đã đóng popup")
                    page.wait_for_timeout(600)
                    return True
        except Exception:
            continue
    return False


def start_new_chat(page):
    try:
        new_chat_selectors = [
            'a[href="/"]',
            'button:has-text("Chat mới")',
            'button:has-text("New chat")',
            'a:has-text("Chat mới")',
            'a:has-text("New chat")',
            '[data-testid="create-new-chat-button"]',
            'nav a[href="/"]',
        ]
        for sel in new_chat_selectors:
            try:
                btn = page.locator(sel).first
                if btn.count() > 0 and btn.is_visible(timeout=1500):
                    btn.click(force=True, timeout=3000)
                    page.wait_for_timeout(1500)
                    print("   🆕 Đã mở Chat mới")
                    dismiss_popups(page)
                    return True
            except Exception:
                continue

        page.goto("https://chatgpt.com/", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        dismiss_popups(page)
        print("   🆕 Đã mở Chat mới (qua URL)")
        return True
    except Exception as e:
        print(f"   ⚠️ Không mở được Chat mới: {e}")
        return False


def wait_for_text_generation(page, step_name=""):
    print(f"   ⏳ Đang chờ GPT xử lý {step_name}...")
    try:
        page.wait_for_selector(STOP_BTN_SELECTOR, timeout=10000)
    except Exception:
        pass
    try:
        page.wait_for_selector(STOP_BTN_SELECTOR, state="detached", timeout=180000)
        print(f"   ✅ Hoàn thành {step_name}")
        page.wait_for_timeout(2000)
    except Exception:
        print(f"   ⚠️ GPT có thể bị kẹt. Đang ép dừng...")
        try:
            page.locator(STOP_BTN_SELECTOR).first.click(timeout=5000)
            page.wait_for_timeout(2000)
        except Exception:
            pass


def wait_for_image_generation_done(page, timeout_ms=180000):
    """
    Nhận biết GPT đã xuất ảnh xong bằng: nút Tạm dừng/Stop không còn nữa.
    Trả về True nếu xong, False nếu timeout / lỗi.
    """
    print("   ⏳ Đang chờ GPT vẽ ảnh (chờ nút Tạm dừng biến mất)...")
    try:
        # Chờ nút Stop xuất hiện (đang generate)
        try:
            page.wait_for_selector(STOP_BTN_SELECTOR, timeout=15000)
            print("   ▶️ Đã thấy nút Tạm dừng — GPT đang xử lý...")
        except Exception:
            print("   ⚠️ Không thấy nút Tạm dừng xuất hiện (có thể generate quá nhanh)")

        # Chờ nút Stop biến mất = generate xong
        page.wait_for_selector(STOP_BTN_SELECTOR, state="detached", timeout=timeout_ms)
        print("   ✅ Nút Tạm dừng đã biến mất — GPT đã xong")
        page.wait_for_timeout(2000)  # UI cập nhật ảnh / nút Share
        return True
    except Exception as e:
        print(f"   ⚠️ Timeout / lỗi chờ nút Tạm dừng: {e}")
        try:
            page.locator(STOP_BTN_SELECTOR).first.click(timeout=3000)
            page.wait_for_timeout(2000)
        except Exception:
            pass
        return False


def upload_image(page, image_path, is_first=False):
    filename = os.path.basename(image_path)
    print(f"   📸 Đang attach ảnh: {filename}")

    count_before = get_attach_count(page)

    def wait_attach_increased(timeout_ms=15000):
        deadline = time.time() + (timeout_ms / 1000.0)
        while time.time() < deadline:
            now = get_attach_count(page)
            if now > count_before:
                return True
            page.wait_for_timeout(400)
        return False

    # ----- Cách cũ -----
    try:
        page.locator('#prompt-textarea').click(force=True, timeout=4000)
        page.wait_for_timeout(400)
        page.locator('#upload-files').set_input_files(image_path, timeout=8000)

        if wait_attach_increased(15000):
            print(f"   ✅ Đã attach xong (cách cũ): {filename} | chip {count_before} → {get_attach_count(page)}")
            page.wait_for_timeout(1000)
            return True
        raise Exception("Số chip không tăng sau set_input_files")
    except Exception as e:
        print(f"   ⚠️ Cách cũ thất bại: {e}")

    # ----- Cách mới -----
    try:
        print("   🔄 Chuyển sang cách upload mới...")
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
        except Exception:
            pass

        count_before = get_attach_count(page)

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
        print("   ✅ Đã chọn file trong File Chooser")

        if wait_attach_increased(15000):
            print(f"   ✅ Đã attach xong (cách mới): {filename} | chip {count_before} → {get_attach_count(page)}")
            page.wait_for_timeout(1000)
            return True

        page.wait_for_timeout(2500)
        now = get_attach_count(page)
        if now > count_before:
            print(f"   ✅ Attach OK (fallback đếm chip): {filename}")
            return True

        imgs = page.locator('form img, main form img').count()
        if imgs > 0:
            print(f"   ✅ Attach OK (fallback thấy {imgs} img trong form): {filename}")
            page.wait_for_timeout(800)
            return True

        raise Exception("Không thấy số chip/ảnh tăng sau upload")

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
        composer.click(force=True, timeout=4000)
        page.wait_for_timeout(400)
        composer.fill(text)
        page.wait_for_timeout(600)
        send_button = page.locator(
            'button[data-testid="send-button"], #composer-submit-button, button[aria-label*="Gửi lời nhắc"]'
        ).first
        send_button.wait_for(state="visible", timeout=8000)
        send_button.click()
        print("   📤 Đã gửi prompt (cách cũ)")
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
        try:
            page.wait_for_function(
                """() => {
                    const btn = document.querySelector('button[type="submit"]');
                    return btn && !btn.disabled;
                }""",
                timeout=6000
            )
        except Exception:
            pass
        send_button.click()
        print("   📤 Đã gửi prompt (cách mới)")
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
    time.sleep(6)
    dismiss_popups(page)
    return browser, page


def safe_close_browser(browser):
    try:
        if browser:
            browser.close()
    except Exception as e:
        print(f"   ⚠️ Lỗi đóng browser: {e}")
    time.sleep(1.5)


def run_chatgpt_automation(anh_mau_path, list_anh_paths, prompt_phan_tich, start_profile_idx=0):
    total_images = len(list_anh_paths)
    current_idx = 0
    profile_idx = start_profile_idx
    downloaded_indices = set()

    today_folder, today_str = get_today_output_folder(app.config['KETQUA_FOLDER'])

    update_progress(
        running=True,
        status="running",
        message=f"Bắt đầu từ Browser {profile_idx + 1}",
        current=0,
        total=total_images,
        profile=profile_idx + 1,
        images=[]
    )

    print(f"📌 Bắt đầu từ Profile {profile_idx + 1}")

    with sync_playwright() as p:
        while current_idx < total_images and profile_idx < len(PROFILES):
            profile_path = PROFILES[profile_idx]
            update_progress(profile=profile_idx + 1, message=f"Đang dùng Browser {profile_idx + 1}")
            browser = None

            try:
                browser, page = open_browser(p, profile_path)

                print(f"\n=== PROFILE {profile_idx + 1} | Gửi lại Ảnh mẫu ===")
                update_progress(message=f"Browser {profile_idx + 1}: Chat mới + ảnh mẫu...")
                start_new_chat(page)
                dismiss_popups(page)

                if not upload_image(page, anh_mau_path, is_first=True):
                    print("❌ Không upload được ảnh mẫu → chuyển profile")
                    safe_close_browser(browser)
                    browser = None
                    profile_idx += 1
                    continue

                send_prompt(page, prompt_phan_tich)
                wait_for_text_generation(page, "Ảnh mẫu")
                dismiss_popups(page)

                while current_idx < total_images:
                    if current_idx in downloaded_indices:
                        current_idx += 1
                        continue

                    anh_path = list_anh_paths[current_idx]
                    print(f"\n=== PROFILE {profile_idx + 1} | Ảnh {current_idx + 1}/{total_images} ===")
                    update_progress(
                        message=f"Browser {profile_idx + 1}: Đang xử lý ảnh {current_idx + 1}/{total_images}"
                    )
                    dismiss_popups(page)

                    if not upload_image(page, anh_path):
                        print(f"   ⚠️ Upload ảnh {current_idx + 1} thất bại → bỏ qua")
                        current_idx += 1
                        continue

                    prompt = PROMPT_CHINH_SUA_DAU if current_idx == 0 else PROMPT_TUONG_TU
                    send_prompt(page, prompt)

                    # ===== NHẬN BIẾT ẢNH XONG: nút Tạm dừng biến mất =====
                    switched_due_to_limit = False

                    # Trong lúc chờ, thỉnh thoảng kiểm tra hết lượt
                    gen_done = False
                    wait_start = time.time()
                    max_wait = 180  # giây

                    # Chờ Stop xuất hiện (ngắn)
                    try:
                        page.wait_for_selector(STOP_BTN_SELECTOR, timeout=15000)
                        print("   ▶️ Đã thấy nút Tạm dừng — GPT đang vẽ...")
                    except Exception:
                        print("   ⚠️ Không thấy nút Tạm dừng (có thể xong quá nhanh)")

                    # Chờ Stop biến mất, đồng thời check limit
                    while time.time() - wait_start < max_wait:
                        if is_limit_reached(page):
                            print(f"\n🚫 HẾT LƯỢT ở Profile {profile_idx + 1}")
                            update_progress(message=f"Hết lượt Browser {profile_idx + 1} → chuyển tiếp...")
                            page.wait_for_timeout(3000)
                            switched_due_to_limit = True
                            break

                        try:
                            # Còn nút Stop không?
                            still_stopping = page.locator(STOP_BTN_SELECTOR).count() > 0
                            if not still_stopping:
                                # Đảm bảo đã từng generate một chút (tránh false positive ngay sau send)
                                if time.time() - wait_start > 3:
                                    print("   ✅ Nút Tạm dừng đã biến mất — GPT đã xong")
                                    gen_done = True
                                    page.wait_for_timeout(2000)
                                    break
                        except Exception:
                            pass

                        page.wait_for_timeout(1500)
                    else:
                        print(f"   ⚠️ Timeout 3 phút chờ nút Tạm dừng → bỏ qua ảnh {current_idx + 1}")
                        current_idx += 1
                        try:
                            page.locator(STOP_BTN_SELECTOR).first.click(timeout=3000)
                            page.wait_for_timeout(1500)
                        except Exception:
                            pass
                        if current_idx < total_images:
                            print("   ⏳ Chờ 5 giây...")
                            page.wait_for_timeout(5000)
                        continue

                    if switched_due_to_limit:
                        break

                    # Generate xong → tải ảnh
                    if gen_done:
                        print("   📥 Đang tải ảnh kết quả...")
                        rel = download_latest_generated_image(
                            page, today_folder, today_str, current_idx + 1
                        )
                        if rel:
                            downloaded_indices.add(current_idx)
                            add_progress_image(rel)
                            update_progress(
                                message=f"Đã tải ảnh {current_idx + 1}/{total_images}"
                            )
                            current_idx += 1
                            dismiss_popups(page)
                        else:
                            print("   ⚠️ Tải thất bại → bỏ qua ảnh này")
                            current_idx += 1

                    if current_idx < total_images and not switched_due_to_limit:
                        print("   ⏳ Chờ 5 giây...")
                        page.wait_for_timeout(5000)

            except Exception as e:
                print(f"❌ Lỗi profile {profile_idx + 1}: {e}")
            finally:
                safe_close_browser(browser)
                browser = None

            if current_idx < total_images:
                profile_idx += 1
            else:
                break

    done_count = len(downloaded_indices)
    if done_count >= total_images:
        update_progress(running=False, status="done", message="🎉 Hoàn thành toàn bộ ảnh!")
        print("\n🎉 HOÀN THÀNH TOÀN BỘ ẢNH!")
    else:
        update_progress(
            running=False,
            status="done",
            message=f"Xong {done_count}/{total_images} ảnh (hết profile hoặc còn thiếu)"
        )
        print(f"\n⚠️ Đã tải: {done_count}/{total_images} ảnh.")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/status')
def status():
    with progress_lock:
        return jsonify(dict(progress))


@app.route('/ketqua/<path:filepath>')
def serve_ketqua(filepath):
    return send_from_directory(app.config['KETQUA_FOLDER'], filepath)


@app.route('/process', methods=['POST'])
def process():
    try:
        with progress_lock:
            if progress["running"]:
                return jsonify({"ok": False, "error": "Tool đang chạy, vui lòng đợi!"}), 400

        anh_mau = request.files.get('anh_mau')
        if not anh_mau or not anh_mau.filename:
            return jsonify({"ok": False, "error": "Chưa chọn ảnh mẫu"}), 400
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
            return jsonify({"ok": False, "error": "Chưa chọn ảnh nào cần chỉnh"}), 400

        loai_sp = request.form.get('loai_sp', 'ao')
        prompt_map = {
            'ao': PROMPT_PHAN_TICH_Ao,
            'vay': PROMPT_PHAN_TICH_VAY,
            'quan': PROMPT_PHAN_TICH_QUAN,
            'ca_set': PROMPT_PHAN_TICH_CA_SET,
            'chan_vay': PROMPT_PHAN_TICH_CHAN_VAY
        }
        prompt_phan_tich = prompt_map.get(loai_sp, PROMPT_PHAN_TICH_Ao)

        selected_browser = request.form.get('browser_profile', '1')
        try:
            start_profile_idx = int(selected_browser) - 1
            if start_profile_idx < 0 or start_profile_idx > 7:
                start_profile_idx = 0
        except Exception:
            start_profile_idx = 0

        print(f"📌 Loại SP: {loai_sp} | Profile: {start_profile_idx + 1}")

        thread = threading.Thread(
            target=run_chatgpt_automation,
            args=(anh_mau_path, list_anh_paths, prompt_phan_tich, start_profile_idx)
        )
        thread.start()

        return jsonify({"ok": True, "total": len(list_anh_paths)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, threaded=True)