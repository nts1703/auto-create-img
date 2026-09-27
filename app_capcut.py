import os
import time
import random
import threading
from flask import Flask, render_template, request
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# ==================== CONFIG ====================
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['KETQUA_FOLDER'] = 'ketqua'

for folder in [app.config['UPLOAD_FOLDER'], app.config['KETQUA_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

# Selector theo đúng giao diện tiếng Anh
SELECTORS = {
    "menu_mau": '#SideMenuTemplates',
    "search_mau": 'input[placeholder*="Search templates"], input[placeholder*="Tìm kiếm mẫu"]',
    "mau_dau_tien": '.lv-template-card-main',
    "dung_mau_nay": 'button:has-text("Use this template"), button:has-text("Dùng mẫu này")',
    "nut_batch_replace": 'button:has-text("Batch replace")',
    "nut_from_computer": '#timeline-upload-and-replace, button:has-text("From computer")',
    "nut_xuat": '#export-video-btn',
    "nut_xuat_xac_nhan": '#export-confirm-button',
    "nut_tai_xuong": 'button:has-text("Download"), button:has-text("Tải xuống"), button.button-UYFu5_',
}
# ===============================================


def wait_and_click(page, selector, timeout=15000, description=""):
    """Chờ element xuất hiện rồi click"""
    try:
        print(f"   ⏳ Đang chờ: {description or selector}")
        page.wait_for_selector(selector, timeout=timeout, state="visible")
        page.locator(selector).first.click(force=True)
        print(f"   ✅ Đã click: {description or selector}")
        page.wait_for_timeout(1000)
        return True
    except Exception as e:
        print(f"   ❌ Lỗi click {description or selector}: {e}")
        return False


def wait_for_download_button(page, timeout=180000):
    """
    Chờ nút Download xuất hiện (tối đa 3 phút).
    """
    print("   ⏳ Đang chờ video render xong (chờ nút Download - tối đa 3 phút)...")
    try:
        page.wait_for_selector(SELECTORS["nut_tai_xuong"], timeout=timeout, state="visible")
        print("   ✅ Đã thấy nút Download → Video đã sẵn sàng!")
        page.wait_for_timeout(2000)
        return True
    except Exception as e:
        print(f"   ⚠️ Timeout 3 phút không thấy nút Download: {e}")
        return False


def run_capcut_automation(so_anh, phong_cach, so_video, tu_khoa, list_anh_paths):
    """
    Logic chính:
    - Lặp lại so_video lần
    - Mỗi lần: Mở Mẫu → Search → Chọn mẫu → Use template
              → Batch replace → From computer → upload ảnh (lặp lại cho từng ảnh)
              → Export → Export confirm → Chờ Download (tối đa 3 phút)
    - Trình duyệt KHÔNG BAO GIỜ tự đóng
    """
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir="browser_data_capcut",
            headless=False,
            accept_downloads=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--start-maximized'
            ],
            no_viewport=True,
        )
        page = browser.new_page()

        print("🌐 Đang mở CapCut Web...")
        page.goto("https://www.capcut.com/", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        print("⚠️  Nếu chưa đăng nhập, hãy đăng nhập thủ công trong trình duyệt...")
        print("   Tool sẽ đợi 15 giây để bạn đăng nhập (nếu cần).")
        page.wait_for_timeout(15000)

        for video_idx in range(1, so_video + 1):
            print(f"\n{'='*50}")
            print(f"🎬 BẮT ĐẦU TẠO VIDEO {video_idx}/{so_video}")
            print(f"{'='*50}")

            try:
                # 1. Click menu Templates
                if not wait_and_click(page, SELECTORS["menu_mau"], description="Nút Templates"):
                    print("   ❌ Không tìm thấy nút Templates. Bỏ qua video này.")
                    continue
                page.wait_for_timeout(2000)

                # 2. Search từ khóa
                print(f"   🔍 Đang search: '{tu_khoa}'")
                search_input = page.locator(SELECTORS["search_mau"]).first
                search_input.click()
                page.wait_for_timeout(400)
                search_input.fill("")
                search_input.fill(tu_khoa)
                page.keyboard.press("Enter")
                print(f"   ✅ Đã search: {tu_khoa}")
                page.wait_for_timeout(3500)

                # 3. Click mẫu đầu tiên
                if not wait_and_click(page, SELECTORS["mau_dau_tien"], description="Mẫu đầu tiên"):
                    print("   ❌ Không tìm thấy mẫu. Bỏ qua video này.")
                    continue
                page.wait_for_timeout(1500)

                # 4. Click "Use this template"
                if not wait_and_click(page, SELECTORS["dung_mau_nay"], description="Use this template"):
                    print("   ❌ Không tìm thấy nút Use this template. Bỏ qua video này.")
                    continue
                page.wait_for_timeout(5000)  # Chờ template load

                # 5. Thay ảnh theo luồng: Batch replace → From computer
                if len(list_anh_paths) >= so_anh:
                    anh_su_dung = random.sample(list_anh_paths, so_anh)
                else:
                    anh_su_dung = list_anh_paths[:so_anh]

                print(f"   🖼️  Sẽ thay {len(anh_su_dung)} ảnh bằng Batch replace...")

                for i, anh_path in enumerate(anh_su_dung):
                    try:
                        print(f"\n   --- Đang thay ảnh {i+1}/{len(anh_su_dung)} ---")

                        # Click Batch replace
                        batch_btn = page.locator(SELECTORS["nut_batch_replace"])
                        batch_btn.first.click(force=True)
                        print("   ✅ Đã click Batch replace")
                        page.wait_for_timeout(1200)

                        # Click From computer
                        from_btn = page.locator(SELECTORS["nut_from_computer"])
                        from_btn.first.click(force=True)
                        print("   ✅ Đã click From computer")
                        page.wait_for_timeout(800)

                        # Lấy input file và upload
                        file_input = page.locator('#timeline-upload-and-replace input[type="file"], button:has-text("From computer") input[type="file"]').last
                        file_input.set_input_files(anh_path)
                        print(f"   ✅ Đã chọn ảnh: {os.path.basename(anh_path)}")
                        page.wait_for_timeout(2500)

                    except Exception as e:
                        print(f"   ❌ Lỗi khi thay ảnh {i+1}: {e}")
                        # Cách dự phòng
                        try:
                            print("   🔄 Thử cách dự phòng...")
                            page.locator('input[type="file"]').last.set_input_files(anh_path)
                            page.wait_for_timeout(2000)
                            print(f"   ✅ Upload thành công bằng cách dự phòng")
                        except Exception as e2:
                            print(f"   ❌ Cách dự phòng cũng lỗi: {e2}")

                page.wait_for_timeout(1500)

                # 6. Click nút Export
                if not wait_and_click(page, SELECTORS["nut_xuat"], description="Nút Export"):
                    print("   ❌ Không tìm thấy nút Export. Bỏ qua video này.")
                    continue
                page.wait_for_timeout(1500)

                # 7. Click Export xác nhận (nếu có)
                try:
                    page.wait_for_selector(SELECTORS["nut_xuat_xac_nhan"], timeout=8000, state="visible")
                    page.locator(SELECTORS["nut_xuat_xac_nhan"]).first.click()
                    print("   ✅ Đã click Export xác nhận")
                except:
                    print("   ℹ️ Không thấy nút Export xác nhận (có thể không cần)")

                # 8. Chờ nút Download (tối đa 3 phút)
                success = wait_for_download_button(page, timeout=180000)

                if success:
                    print(f"   🎉 VIDEO {video_idx}/{so_video} HOÀN THÀNH!")
                    try:
                        page.locator(SELECTORS["nut_tai_xuong"]).first.click()
                        page.wait_for_timeout(3000)
                        print("   💾 Đã click Download")
                    except:
                        pass
                else:
                    print(f"   ⚠️ VIDEO {video_idx} timeout 3 phút, bỏ qua.")

                # Nghỉ rồi làm video tiếp theo
                if video_idx < so_video:
                    print("   ⏳ Nghỉ 4 giây trước khi tạo video tiếp theo...")
                    page.wait_for_timeout(4000)
                    try:
                        page.goto("https://www.capcut.com/", wait_until="domcontentloaded")
                        page.wait_for_timeout(3000)
                    except:
                        pass

            except Exception as e:
                print(f"   ❌ Lỗi không mong muốn ở video {video_idx}: {e}")
                continue

        print(f"\n{'='*50}")
        print(f"🏁 ĐÃ XỬ LÝ XONG {so_video} VIDEO.")
        print("Trình duyệt VẪN ĐƯỢC GIỮ MỞ để bạn kiểm tra.")
        print("Bạn muốn đóng thì tự tắt cửa sổ trình duyệt.")
        print(f"{'='*50}")

        # Giữ trình duyệt mở mãi
        try:
            while True:
                page.wait_for_timeout(60000)
        except:
            pass


@app.route('/')
def index():
    return render_template('index_capcut.html')


@app.route('/process', methods=['POST'])
def process():
    try:
        so_anh = int(request.form.get('so_anh', 2))
        phong_cach = request.form.get('phong_cach', 'nhẹ nhàng')
        so_video = int(request.form.get('so_video', 1))
        tu_khoa = request.form.get('tu_khoa', f'{so_anh} ảnh {phong_cach}')

        files = request.files.getlist('images')
        if not files or len(files) == 0:
            return "Chưa chọn ảnh nào!", 400

        list_anh_paths = []
        for file in files:
            if file.filename:
                path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(path)
                list_anh_paths.append(path)

        if len(list_anh_paths) < so_anh:
            return f"Bạn cần ít nhất {so_anh} ảnh!", 400

        print(f"\n📌 Cấu hình nhận được:")
        print(f"   - Số ảnh   : {so_anh}")
        print(f"   - Phong cách: {phong_cach}")
        print(f"   - Số video : {so_video}")
        print(f"   - Từ khóa  : {tu_khoa}")
        print(f"   - Số file  : {len(list_anh_paths)}")

        thread = threading.Thread(
            target=run_capcut_automation,
            args=(so_anh, phong_cach, so_video, tu_khoa, list_anh_paths)
        )
        thread.start()

        return f"Tool đang chạy ngầm! Sẽ tạo {so_video} video với từ khóa « {tu_khoa} ». Hãy xem Terminal để theo dõi tiến trình."

    except Exception as e:
        return f"Lỗi: {str(e)}", 500


if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)

    html_src = 'index_capcut.html'
    html_dst = os.path.join('templates', 'index_capcut.html')
    if os.path.exists(html_src) and not os.path.exists(html_dst):
        import shutil
        shutil.copy(html_src, html_dst)

    print("🚀 CapCut Auto Tool đang chạy tại http://127.0.0.1:5000")
    app.run(debug=True, port=5000)