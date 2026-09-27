import os
import time
import threading
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
# ===============================================


PROMPT_PHAN_TICH_Ao = "Hãy phân tích chi tiết chiếc áo trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ. Phân biệt rõ đâu là mặt trước và sau chiếc áo"
PROMPT_PHAN_TICH_VAY = "Hãy phân tích chi tiết chiếc váy trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."
PROMPT_PHAN_TICH_QUAN = "Hãy phân tích chi tiết chiếc quần trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."
PROMPT_PHAN_TICH_CA_SET = "Hãy phân tích chi tiết cả set trang phục trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."
PROMPT_PHAN_TICH_CHAN_VAY = "Hãy phân tích chi tiết chân váy trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."


PROMPT_CHINH_SUA_DAU = "Hãy chỉnh sửa ảnh này để người trong ảnh mặc đúng bộ đồ mà bạn vừa phân tích ở tin nhắn trước. Giữ nguyên tư thế, gương mặt, ánh sáng, background và chất lượng ảnh gốc. Chỉ thay đổi trang phục. độ nét 4k"
PROMPT_TUONG_TU = "Hãy chỉnh sửa ảnh này để người trong ảnh mặc đúng bộ đồ mà bạn vừa phân tích ở tin nhắn trước. Giữ nguyên tư thế, gương mặt, ánh sáng, background và chất lượng ảnh gốc. Chỉ thay đổi trang phục. độ nét 4k"


# Selector bắt nút tải xuống hoặc ảnh do GPT tạo ra
RESULT_SELECTOR = (
    'button[aria-label*="Download"], button[aria-label*="Tải xuống"], '
    'img[alt*="Generated image"], img[alt*="Hình ảnh được tạo"], '
    'button[aria-label*="Chia sẻ hình ảnh"], '
    'button[aria-label*="Bắt đầu Chế độ thoại"], '
    'button[aria-label*="Chế độ thoại"]'
)


def wait_for_text_generation(page, step_name=""):
    """Chờ GPT phân tích chữ (Dùng cho Ảnh mẫu)"""
    print(f"   ⏳ Đang chờ GPT xử lý {step_name}...")
    stop_btn_selector = 'button[aria-label*="Stop"], button[aria-label*="Dừng"]'
    try:
        page.wait_for_selector(stop_btn_selector, timeout=10000)
    except:
        pass
    try:
        page.wait_for_selector(stop_btn_selector, state="detached", timeout=180000)
        print(f"   ✅ Hoàn thành {step_name}")
        page.wait_for_timeout(3000)
    except Exception as e:
        print(f"   ⚠️ GPT có thể bị kẹt. Đang ép dừng...")
        try:
            page.locator(stop_btn_selector).first.click(timeout=5000)
            page.wait_for_timeout(3000)
        except:
            pass


def upload_image(page, image_path, is_first=False):
    """Upload ảnh bằng nút + → Thêm ảnh & tệp (File Chooser)"""
    filename = os.path.basename(image_path)
    print(f"   📸 Đang attach ảnh: {filename}")
    try:
        # 1. Click nút dấu +
        plus_btn = page.locator('button[aria-label="Thêm tệp và nội dung khác"]').first
        plus_btn.wait_for(state="visible", timeout=10000)
        plus_btn.click()
        page.wait_for_timeout(700)

        # 2. Click menu "Thêm ảnh & tệp" + bắt File Chooser
        with page.expect_file_chooser(timeout=15000) as fc_info:
            menu_item = page.locator('button:has-text("Thêm ảnh & tệp")').first
            menu_item.wait_for(state="visible", timeout=8000)
            menu_item.click()

        file_chooser = fc_info.value
        file_chooser.set_files(image_path)
        print(f"   ✅ Đã chọn file trong File Chooser")

        # 3. Chờ ảnh được gắn (nhanh – chỉ tối đa ~6 giây)
        combined_selector = (
            'button[aria-label*="Remove"], button[aria-label*="Xóa"], '
            'button[aria-label*="Remove file"], button[aria-label*="Xóa tệp"], '
            '[data-testid*="file-thumbnail"], [data-testid*="attachment"], '
            'img[alt*="Uploaded"], div[class*="attachment"] img, '
            'div[class*="file"] img, button[aria-label*="Close"]'
        )

        try:
            page.wait_for_selector(combined_selector, timeout=6000)
            print(f"   ✅ Phát hiện ảnh đã gắn")
        except:
            # Fallback nhanh
            page.wait_for_timeout(2000)
            imgs = page.locator('form img, [data-testid="composer"] img').count()
            if imgs == 0:
                raise Exception("Không thấy dấu hiệu ảnh đã được gắn vào prompt")
            print(f"   ✅ Phát hiện {imgs} ảnh trong composer (fallback)")

        print(f"   ✅ Đã attach xong: {filename}")
        return True

    except Exception as e:
        print(f"   ❌ Lỗi attach {filename}: {e}")
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
        except:
            pass
        return False


def send_prompt(page, text):
    """Điền prompt vào ProseMirror và bấm nút Gửi"""
    try:
        # === Ô nhập prompt (ProseMirror) ===
        composer = page.locator(
            'div.ProseMirror[contenteditable="true"], '
            'div[contenteditable="true"][role="textbox"], '
            '[data-composer-markdown][contenteditable="true"], '
            'div[aria-label*="Hỏi ChatGPT"], div[aria-label*="Ask ChatGPT"]'
        ).first

        composer.wait_for(state="visible", timeout=15000)
        composer.click(force=True)
        page.wait_for_timeout(400)

        # Xóa nội dung cũ (nếu có)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.wait_for_timeout(200)

        # Điền prompt
        page.keyboard.type(text, delay=8)
        page.wait_for_timeout(600)

        # === Nút Gửi ===
        send_button = page.locator(
            'button[type="submit"]:not([disabled]), '
            'button[aria-label*="Gửi"], button[aria-label*="Send"], '
            'button[data-testid="send-button"], '
            'button[aria-label="Gửi"], button[aria-label="Send prompt"]'
        ).first

        send_button.wait_for(state="visible", timeout=10000)

        # Đợi nút không bị disabled (tối đa 8 giây)
        try:
            page.wait_for_function(
                """() => {
                    const btn = document.querySelector('button[type="submit"]');
                    return btn && !btn.disabled;
                }""",
                timeout=8000
            )
        except:
            pass

        send_button.click()
        print(f"   📤 Đã gửi prompt (bằng nút Gửi)")

    except Exception as e:
        print(f"   ⚠️ Lỗi khi click nút gửi: {e}")
        print("   🔄 Thử fallback dùng phím Enter...")
        try:
            page.keyboard.press("Enter")
        except:
            pass


def run_chatgpt_automation(anh_mau_path, list_anh_paths, prompt_phan_tich):
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir="browser_data",
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        page = browser.new_page()

        print("🌐 Mở ChatGPT...")
        page.goto("https://chatgpt.com/")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(8)

        print("\n=== XỬ LÝ ẢNH MẪU ===")
        if not upload_image(page, anh_mau_path, is_first=True):
            print("❌ Không upload được ảnh mẫu → dừng")
            return

        send_prompt(page, prompt_phan_tich)
        wait_for_text_generation(page, "Ảnh mẫu")

        for idx, anh_path in enumerate(list_anh_paths):
            print(f"\n=== XỬ LÝ ẢNH {idx+1}/{len(list_anh_paths)} ===")

            # 1. Đếm số lượng kết quả hiện tại
            current_results_count = page.locator(RESULT_SELECTOR).count()

            # 2. Upload và Gửi Prompt
            if not upload_image(page, anh_path):
                print(f"   ⚠️ Bỏ qua ảnh {idx+1} vì upload thất bại")
                continue

            prompt = PROMPT_CHINH_SUA_DAU if idx == 0 else PROMPT_TUONG_TU
            send_prompt(page, prompt)

            # 3. Chờ ảnh mới được tạo
            print(f"   ⏳ Đang chờ GPT vẽ ảnh (tối đa 3 phút)...")
            try:
                page.wait_for_function(
                    "([selector, count]) => document.querySelectorAll(selector).length > count",
                    arg=[RESULT_SELECTOR, current_results_count],
                    timeout=180000
                )
                print(f"   🎨✅ Ảnh {idx+1} đã được vẽ xong!")
                # page.wait_for_timeout(3000)
            except Exception as e:
                print(f"   ⚠️ Quá 3 phút không thấy ảnh mới. Bỏ qua...")
                try:
                    page.locator('button[aria-label*="Stop"], button[aria-label*="Dừng"]').first.click(timeout=3000)
                    page.wait_for_timeout(2000)
                except:
                    pass

        print("\n🎉 HOÀN THÀNH TOÀN BỘ QUY TRÌNH!")
        # browser.close()   # giữ trình duyệt mở để bạn kiểm tra


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

        return "Tool đang chạy ngầm! Hãy mở Terminal/CMD của Python để xem tiến trình từng ảnh."

    except Exception as e:
        return f"Lỗi: {str(e)}", 500


if __name__ == '__main__':
    app.run(debug=True)