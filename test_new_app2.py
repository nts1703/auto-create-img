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
# ===============================================

PROMPT_PHAN_TICH_Ao = "Hãy phân tích chi tiết chiếc áo trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ. Phân biệt rõ đâu là mặt trước và sau chiếc áo"
PROMPT_PHAN_TICH_VAY = "Hãy phân tích chi tiết chiếc váy trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."
PROMPT_PHAN_TICH_QUAN = "Hãy phân tích chi tiết chiếc quần trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."
PROMPT_PHAN_TICH_CA_SET = "Hãy phân tích chi tiết cả set trang phục trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."
PROMPT_PHAN_TICH_CHAN_VAY = "Hãy phân tích chi tiết chân váy trong ảnh này. Mô tả màu sắc, kiểu dáng, chất liệu, chi tiết nổi bật và cách phối đồ."

PROMPT_CHINH_SUA_DAU = "Hãy chỉnh sửa ảnh này để người trong ảnh mặc đúng bộ đồ mà bạn vừa phân tích ở tin nhắn trước. Giữ nguyên tư thế, gương mặt, ánh sáng, background và chất lượng ảnh gốc. Chỉ thay đổi trang phục. độ nét 4k"
PROMPT_TUONG_TU = "Hãy chỉnh sửa ảnh này để người trong ảnh mặc đúng bộ đồ mà bạn vừa phân tích ở tin nhắn trước. Giữ nguyên tư thế, gương mặt, ánh sáng, background và chất lượng ảnh gốc. Chỉ thay đổi trang phục. độ nét 4k"

# Selector bắt nút Share trên bức ảnh vừa tạo xong
RESULT_SELECTOR = (
    'button[aria-label="Chia sẻ hình ảnh này"], '
    'button[aria-label*="Chia sẻ hình ảnh"], '
    'button[aria-label*="Share this image"]'
)


def get_today_output_folder(base_folder='ketqua'):
    """Tạo thư mục lưu ảnh theo ngày: ketqua/YYYY-MM-DD/"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    folder_path = os.path.join(base_folder, today_str)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


def download_latest_generated_image(page, output_dir, image_index):
    """Bấm Share -> Bấm Tải xuống -> Lưu file về thư mục dự án"""
    try:
        last_assistant_turn = page.locator('article, div[data-message-author-role="assistant"]').last
        if not last_assistant_turn.is_visible():
            return False

        # Hover nhẹ vào ảnh phòng trường hợp nút bị ẩn
        try:
            img_el = last_assistant_turn.locator('img').last
            if img_el.count() > 0 and img_el.is_visible():
                img_el.hover(timeout=1000)
                page.wait_for_timeout(300)
        except Exception:
            pass

        # 1. Tìm và click nút Chia sẻ trên ảnh mới nhất
        share_btn = last_assistant_turn.locator(RESULT_SELECTOR).last
        if not share_btn.is_visible(timeout=3000):
            print("   ⚠️ Không tìm thấy nút Chia sẻ trên ảnh mới")
            return False

        print("   📤 Bấm nút Chia sẻ, chờ menu mở...")
        share_btn.click(force=True)
        page.wait_for_timeout(800)

        # 2. Tìm nút Tải xuống trong menu thả xuống
        download_btn = page.locator(
            'button.interactive-button:has-text("Tải xuống"), '
            'button:has-text("Tải xuống"), '
            'button:has-text("Download")'
        ).last

        if not download_btn.is_visible(timeout=3000):
            print("   ⚠️ Không tìm thấy nút Tải xuống trong menu")
            page.keyboard.press("Escape")
            return False

        # 3. Tải và lưu file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"anh_tao_{image_index:02d}_{timestamp}.png"
        save_path = os.path.join(output_dir, file_name)

        print("   📥 Đang tải file về máy...")
        with page.expect_download(timeout=15000) as download_info:
            download_btn.click(force=True)

        download = download_info.value
        download.save_as(save_path)
        print(f"   💾✅ ĐÃ LƯU ẢNH THÀNH CÔNG: {save_path}")

        page.wait_for_timeout(500)
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

        return True

    except Exception as e:
        print(f"   ⚠️ Lỗi trong quá trình tải ảnh: {e}")
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return False


def wait_for_text_generation(page, step_name=""):
    """Chờ GPT phân tích chữ (Dùng cho Ảnh mẫu)"""
    print(f"   ⏳ Đang chờ GPT xử lý {step_name}...")
    stop_btn_selector = 'button[aria-label*="Stop"], button[aria-label*="Dừng"]'
    try:
        page.wait_for_selector(stop_btn_selector, timeout=10000)
    except Exception:
        pass
    try:
        page.wait_for_selector(stop_btn_selector, state="detached", timeout=180000)
        print(f"   ✅ Hoàn thành {step_name}")
        page.wait_for_timeout(3000)
    except Exception:
        print(f"   ⚠️ GPT có thể bị kẹt. Đang ép dừng...")
        try:
            page.locator(stop_btn_selector).first.click(timeout=5000)
            page.wait_for_timeout(3000)
        except Exception:
            pass


def upload_image(page, image_path, is_first=False):
    """Đính kèm ảnh vào ô chat chuẩn xác và chờ thumbnail tải xong"""
    filename = os.path.basename(image_path)
    print(f"   📸 Đang đính kèm ảnh: {filename}")
    try:
        # Focus ô nhập prompt
        page.locator('#prompt-textarea').first.click(force=True)
        page.wait_for_timeout(300)
        
        # Nạp file trực tiếp vào input ngầm của trang
        file_input = page.locator('input[type="file"]').first
        file_input.set_input_files(image_path)
        
        # Chờ thumbnail/nút Xóa tệp xuất hiện (đảm bảo ảnh đã load xong vào ô chat)
        page.wait_for_selector(
            'button[aria-label*="Remove"], button[aria-label*="Xóa"], [data-testid*="attachment"]', 
            timeout=15000
        )
        print(f"   ✅ Đã attach thành công: {filename}")
        page.wait_for_timeout(1500)
        return True
    except Exception as e:
        print(f"   ❌ Lỗi attach {filename}: {e}")
        return False


def send_prompt(page, text):
    """Điền prompt và gửi"""
    try:
        composer = page.locator('#prompt-textarea').first
        composer.click(force=True)
        page.wait_for_timeout(300)
        composer.fill(text)
        page.wait_for_timeout(800)

        send_button = page.locator('button[data-testid="send-button"], #composer-submit-button, button[aria-label*="Gửi lời nhắc"]').first
        send_button.wait_for(state="visible", timeout=10000)
        send_button.click()
        print(f"   📤 Đã gửi prompt")
        
    except Exception as e:
        print(f"   ⚠️ Lỗi click nút gửi: {e}. Thử phím Enter...")
        try:
            page.keyboard.press("Enter")
        except Exception:
            pass


def run_chatgpt_automation(anh_mau_path, list_anh_paths, prompt_phan_tich):
    today_folder = get_today_output_folder(app.config['KETQUA_FOLDER'])

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir="browser_data_8", 
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        page = browser.new_page()
        
        print("🌐 Mở ChatGPT...")
        page.goto("https://chatgpt.com/")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(10)

        # 1. XỬ LÝ ẢNH MẪU
        print("\n=== XỬ LÝ ẢNH MẪU ===")
        if upload_image(page, anh_mau_path, is_first=True):
            send_prompt(page, prompt_phan_tich)
            wait_for_text_generation(page, "Ảnh mẫu")
        else:
            print("   ❌ Không thể đính kèm ảnh mẫu. Dừng tiến trình!")
            return

        # 2. XỬ LÝ DANH SÁCH ẢNH CẦN CHỈNH SỬA
        for idx, anh_path in enumerate(list_anh_paths):
            print(f"\n=== XỬ LÝ ẢNH {idx+1}/{len(list_anh_paths)} ===")
            
            # Đếm số kết quả hiện tại
            current_results_count = page.locator(RESULT_SELECTOR).count()
            
            # Đính kèm ảnh (Chỉ gửi prompt khi attach thành công)
            if not upload_image(page, anh_path):
                print(f"   ⚠️ Đính kèm ảnh {anh_path} thất bại. Bỏ qua để không bị gửi thiếu ảnh.")
                continue

            # Gửi prompt sau khi đính kèm ảnh thành công
            prompt = PROMPT_CHINH_SUA_DAU if idx == 0 else PROMPT_TUONG_TU
            send_prompt(page, prompt)
            
            # Chờ vẽ ảnh xong & Tải ảnh về
            print(f"   ⏳ Đang chờ GPT vẽ ảnh (Tối đa 3 phút)...")
            try:
                page.wait_for_function(
                    "([selector, count]) => document.querySelectorAll(selector).length > count",
                    arg=[RESULT_SELECTOR, current_results_count],
                    timeout=180000
                )
                print(f"   🎨✅ Ảnh {idx+1} đã vẽ xong!")
                page.wait_for_timeout(2000)
                
                # Tải ảnh về máy
                download_latest_generated_image(page, today_folder, idx + 1)
                
            except Exception as e:
                print(f"   ⚠️ Quá 3 phút không thấy ảnh mới hoặc gặp lỗi: {e}")
                try:
                    page.locator('button[aria-label*="Stop"], button[aria-label*="Dừng"]').first.click(timeout=3000)
                    page.wait_for_timeout(2000)
                except Exception:
                    pass

        print("\n🎉 HOÀN THÀNH TOÀN BỘ QUY TRÌNH!")


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
        print(f"📌 Prompt phân tích: {prompt_phan_tich[:80]}...")

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