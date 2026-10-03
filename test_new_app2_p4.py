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

# ===== Trạng thái tiến trình (chia sẻ giữa thread) =====
progress_lock = threading.Lock()
progress = {
    "running": False,
    "status": "idle",          # idle | running | done | error
    "message": "",
    "current": 0,
    "total": 0,
    "profile": 0,
    "images": []               # list đường dẫn relative: "2026-10-03/anh_tao_01_....png"
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

# Prompt cách dự phòng: ảnh 1 = cần chỉnh, ảnh 2 = mẫu
PROMPT_DU_PHONG = (
    "Có 2 ảnh được đính kèm theo thứ tự: "
    "ảnh 1 là ảnh cần chỉnh, ảnh 2 là ảnh mẫu trang phục. "
    "Hãy chỉnh sửa ảnh 1 để người trong ảnh 1 mặc đúng bộ đồ của người trong ảnh 2. "
    "Giữ nguyên tư thế, gương mặt, ánh sáng, background và chất lượng ảnh gốc của ảnh 1. "
    "Chỉ thay đổi trang phục. Độ nét 4K."
)

SHARE_ON_IMAGE = (
    'button[aria-label="Chia sẻ hình ảnh này"], '
    'button[aria-label*="Chia sẻ hình ảnh"], '
    'button[aria-label*="Share this image"]'
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


def get_today_output_folder(base_folder='ketqua'):
    today_str = datetime.now().strftime("%Y-%m-%d")
    folder_path = os.path.join(base_folder, today_str)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path, today_str


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
            except:
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
        except:
            pass

        rel_path = f"{today_str}/{file_name}"
        return rel_path

    except Exception as e:
        print(f"   ⚠️ Lỗi tải ảnh: {e}")
        try:
            page.keyboard.press("Escape")
        except:
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


def upload_two_images_then_prompt(page, anh_can_chinh_path, anh_mau_path, prompt_text):
    """Cách dự phòng: upload ảnh cần chỉnh TRƯỚC → ảnh mẫu SAU → gửi 1 prompt."""
    print("   📸 [Dự phòng] Upload ảnh cần chỉnh trước...")
    if not upload_image(page, anh_can_chinh_path):
        print("   ❌ [Dự phòng] Upload ảnh cần chỉnh thất bại")
        return False

    print("   📸 [Dự phòng] Upload ảnh mẫu tiếp...")
    if not upload_image(page, anh_mau_path):
        print("   ❌ [Dự phòng] Upload ảnh mẫu thất bại")
        return False

    print("   📤 [Dự phòng] Gửi prompt...")
    send_prompt(page, prompt_text)
    return True


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


def run_fallback_single_browser(anh_mau_path, list_anh_paths, pending_indices, profile_idx):
    """
    Cách dự phòng — chỉ 1 browser (browser user chọn).
    Tắt rồi bật lại browser đó.
    Mỗi ảnh: up ảnh cần chỉnh → up ảnh mẫu → 1 prompt.
    Hết lượt → báo và dừng, không chuyển browser khác.
    """
    if not pending_indices:
        return set()

    print(f"\n{'='*50}")
    print(f"🔁 BẮT ĐẦU CÁCH DỰ PHÒNG (chỉ Browser {profile_idx + 1})")
    print(f"   Còn {len(pending_indices)} ảnh chưa chỉnh được")
    print(f"{'='*50}")

    update_progress(
        status="running",
        running=True,
        message=f"Cách dự phòng — Browser {profile_idx + 1}",
        profile=profile_idx + 1
    )

    today_folder, today_str = get_today_output_folder(app.config['KETQUA_FOLDER'])
    newly_done = set()
    profile_path = PROFILES[profile_idx]

    with sync_playwright() as p:
        browser, page = open_browser(p, profile_path)

        try:
            for idx in pending_indices:
                if is_limit_reached(page):
                    print(f"\n🚫 [Dự phòng] Hết lượt ở Browser {profile_idx + 1} → dừng, không chuyển browser")
                    update_progress(message=f"Dự phòng: hết lượt Browser {profile_idx + 1}, đã dừng")
                    break

                anh_path = list_anh_paths[idx]
                print(f"\n=== [DỰ PHÒNG] Ảnh {idx + 1}/{len(list_anh_paths)} ===")
                update_progress(
                    message=f"Dự phòng Browser {profile_idx + 1}: ảnh {idx + 1}/{len(list_anh_paths)}"
                )
                dismiss_popups(page)

                share_count_before = get_share_count(page)

                ok = upload_two_images_then_prompt(
                    page, anh_path, anh_mau_path, PROMPT_DU_PHONG
                )
                if not ok:
                    print(f"   ⚠️ [Dự phòng] Bỏ qua ảnh {idx + 1}")
                    continue

                print(f"   ⏳ [Dự phòng] Chờ GPT vẽ (tối đa 3 phút)...")
                start_time = time.time()
                timeout_seconds = 180
                got_image = False

                page.wait_for_timeout(8000)

                while time.time() - start_time < timeout_seconds:
                    if is_limit_reached(page):
                        print(f"\n🚫 [Dự phòng] Hết lượt → dừng hẳn")
                        update_progress(message=f"Dự phòng: hết lượt Browser {profile_idx + 1}")
                        try:
                            browser.close()
                        except Exception:
                            pass
                        return newly_done

                    try:
                        if get_share_count(page) > share_count_before:
                            print("   ✅ [Dự phòng] Có ảnh mới, đang tải...")
                            page.wait_for_timeout(1500)
                            rel = download_latest_generated_image(
                                page, today_folder, today_str, idx + 1
                            )
                            if rel:
                                newly_done.add(idx)
                                add_progress_image(rel)
                                update_progress(message=f"Dự phòng: đã tải ảnh {idx + 1}")
                                got_image = True
                                dismiss_popups(page)
                                break
                    except Exception:
                        pass

                    page.wait_for_timeout(3000)
                else:
                    print(f"   ⚠️ [Dự phòng] Timeout ảnh {idx + 1}")
                    try:
                        page.locator(
                            'button[aria-label*="Stop"], button[aria-label*="Dừng"]'
                        ).first.click(timeout=3000)
                    except Exception:
                        pass

                if not got_image and is_limit_reached(page):
                    break

                page.wait_for_timeout(10000)

        finally:
            try:
                browser.close()
            except Exception:
                pass

    return newly_done


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

    # ========== LOGIC CŨ (giữ nguyên) ==========
    with sync_playwright() as p:
        while current_idx < total_images and profile_idx < len(PROFILES):
            profile_path = PROFILES[profile_idx]
            update_progress(profile=profile_idx + 1, message=f"Đang dùng Browser {profile_idx + 1}")
            browser, page = open_browser(p, profile_path)

            try:
                print(f"\n=== PROFILE {profile_idx + 1} | Gửi lại Ảnh mẫu ===")
                update_progress(message=f"Browser {profile_idx + 1}: Gửi ảnh mẫu...")
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
                    if current_idx in downloaded_indices:
                        current_idx += 1
                        continue

                    anh_path = list_anh_paths[current_idx]
                    print(f"\n=== PROFILE {profile_idx + 1} | Ảnh {current_idx + 1}/{total_images} ===")
                    update_progress(
                        message=f"Browser {profile_idx + 1}: Đang xử lý ảnh {current_idx + 1}/{total_images}"
                    )
                    dismiss_popups(page)

                    share_count_before = get_share_count(page)

                    if not upload_image(page, anh_path):
                        print(f"   ⚠️ Upload ảnh {current_idx + 1} thất bại → bỏ qua")
                        current_idx += 1
                        continue

                    prompt = PROMPT_CHINH_SUA_DAU if current_idx == 0 else PROMPT_TUONG_TU
                    send_prompt(page, prompt)

                    print(f"   ⏳ Đang chờ GPT vẽ ảnh mới (tối đa 3 phút)...")
                    start_time = time.time()
                    timeout_seconds = 180
                    check_interval = 3
                    switched_due_to_limit = False

                    page.wait_for_timeout(8000)

                    while time.time() - start_time < timeout_seconds:
                        if is_limit_reached(page):
                            print(f"\n🚫 HẾT LƯỢT ở Profile {profile_idx + 1}")
                            update_progress(message=f"Hết lượt Browser {profile_idx + 1} → chuyển tiếp...")
                            page.wait_for_timeout(3000)
                            switched_due_to_limit = True
                            break

                        try:
                            share_count_now = get_share_count(page)
                            if share_count_now > share_count_before:
                                print("   ✅ Phát hiện Share MỚI! Đang tải...")
                                page.wait_for_timeout(1500)

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
                                    break
                                else:
                                    print("   ⚠️ Tải thất bại")
                                    break
                        except Exception:
                            pass

                        page.wait_for_timeout(check_interval * 1000)
                    else:
                        print(f"   ⚠️ Timeout → bỏ qua ảnh {current_idx + 1}")
                        current_idx += 1
                        try:
                            page.locator('button[aria-label*="Stop"], button[aria-label*="Dừng"]').first.click(timeout=3000)
                            page.wait_for_timeout(1500)
                        except Exception:
                            pass

                    if switched_due_to_limit:
                        break

                    if current_idx < total_images and not switched_due_to_limit:
                        print("   ⏳ Chờ 15 giây...")
                        page.wait_for_timeout(15000)

            finally:
                try:
                    browser.close()
                except Exception:
                    pass

            if current_idx < total_images:
                profile_idx += 1
            else:
                break

    # ========== CÁCH DỰ PHÒNG (chỉ 1 browser = browser chọn lúc đầu) ==========
    pending = [i for i in range(total_images) if i not in downloaded_indices]

    if pending:
        print(f"\n⚠️ Còn {len(pending)} ảnh chưa chỉnh được → chạy CÁCH DỰ PHÒNG")
        extra = run_fallback_single_browser(
            anh_mau_path,
            list_anh_paths,
            pending,
            start_profile_idx
        )
        downloaded_indices |= extra

    done_count = len(downloaded_indices)
    if done_count >= total_images:
        update_progress(running=False, status="done", message="🎉 Hoàn thành toàn bộ ảnh!")
        print("\n🎉 HOÀN THÀNH TOÀN BỘ ẢNH!")
    else:
        update_progress(
            running=False,
            status="done",
            message=f"Xong {done_count}/{total_images} ảnh (kể cả dự phòng; hết lượt thì đã dừng)"
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
        except:
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