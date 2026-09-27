import os
import time
import random
import datetime
from flask import Flask, render_template, request
from playwright.sync_api import sync_playwright

app = Flask(__name__)
app.config['UPLOADS_CAPCUT'] = 'uploads_capcut'
app.config['VIDEOS_CAPCUT'] = 'videos_capcut'

for folder in [app.config['UPLOADS_CAPCUT'], app.config['VIDEOS_CAPCUT']]:
    os.makedirs(folder, exist_ok=True)


def run_capcut_automation(all_image_paths, total_videos=5, images_per_video=3):
    user_data_dir = os.path.join(os.getcwd(), "capcut_browser_data")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    successful_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        page = browser.new_page()

        for i in range(total_videos):
            print(f"\n🎬 === [BẮT ĐẦU] TẠO VIDEO {i+1}/{total_videos} ===")
            
            try:
                # 1. Truy cập trang mẫu
                print("1️⃣ Truy cập kho mẫu CapCut...")
                page.goto("https://www.capcut.com/templates", timeout=60000)
                page.wait_for_load_state("networkidle", timeout=30000)
                time.sleep(4)

                # 2. Chọn mẫu ngẫu nhiên
                print("2️⃣ Chọn mẫu ngẫu nhiên...")
                cards = page.locator('a[href*="/template-detail/"]').all()
                if not cards:
                    print("❌ Không tìm thấy mẫu nào!")
                    continue
                
                selected_card = random.choice(cards[:10])
                selected_card.click()
                time.sleep(5)

                # 3. Sử dụng mẫu
                print("3️⃣ Mở trình biên tập...")
                use_btn = page.locator('button:has-text("Use template"), button:has-text("Sử dụng mẫu"), button:has-text("Use this template")').first
                use_btn.wait_for(state="visible", timeout=20000)
                use_btn.click()
                
                page.wait_for_timeout(8000)  # Chờ editor load

                # 4. Upload ảnh
                print(f"4️⃣ Đang upload {images_per_video} ảnh...")
                file_inputs = page.locator('input[type="file"]').all()
                
                if not file_inputs:
                    print("⚠️ Không tìm thấy input upload ảnh!")
                    continue

                num_to_use = min(images_per_video, len(all_image_paths), len(file_inputs))
                selected_photos = random.sample(all_image_paths, num_to_use)

                for idx, photo_path in enumerate(selected_photos):
                    file_inputs[idx].set_input_files(photo_path)
                    print(f"   → Upload ảnh {idx+1}/{num_to_use}")
                    page.wait_for_timeout(1200)

                page.wait_for_timeout(5000)  # Chờ render

                # 5. Export
                print("5️⃣ Bấm Export...")
                export_btn = page.locator('button:has-text("Export"), button:has-text("Xuất")').first
                export_btn.click()
                time.sleep(3)

                # 6. Tải xuống không watermark
                print("6️⃣ Chọn tải xuống...")
                download_btn = page.locator(
                    'button:has-text("Export without watermark"), button:has-text("Download"), button:has-text("Tải xuống")'
                ).first
                download_btn.click()

                # 7. Chờ tải file
                print("⏳ Đang render và tải video (có thể mất 20-50 giây)...")
                output_video_path = os.path.join(
                    app.config['VIDEOS_CAPCUT'], 
                    f"video_{timestamp}_{i+1:02d}.mp4"
                )

                with page.expect_download(timeout=180000) as download_info:
                    pass

                download = download_info.value
                download.save_as(output_video_path)
                
                print(f"✅ THÀNH CÔNG! Video {i+1} đã lưu: {output_video_path}")
                successful_count += 1
                time.sleep(6)

            except Exception as e:
                print(f"❌ Lỗi video {i+1}: {str(e)}")
                time.sleep(5)
                continue

        browser.close()
        return successful_count


@app.route('/')
def index():
    return render_template('index3.html')


@app.route('/process_capcut', methods=['POST'])
def process_capcut():
    try:
        if 'danhsach_anh' not in request.files:
            return "Không tìm thấy file ảnh!", 400

        files = request.files.getlist('danhsach_anh')
        if not files or files[0].filename == '':
            return "Vui lòng chọn ít nhất một ảnh!", 400

        # Lấy config từ form
        video_count = int(request.form.get('video_count', 5))
        images_per_video = int(request.form.get('images_per_video', 3))

        # Lưu ảnh
        list_anh_paths = []
        for file in files:
            if file.filename:
                path = os.path.join(app.config['UPLOADS_CAPCUT'], file.filename)
                file.save(path)
                list_anh_paths.append(path)

        if len(list_anh_paths) < images_per_video:
            return f"Cần ít nhất {images_per_video} ảnh để tạo video!", 400

        # Chạy automation
        count = run_capcut_automation(
            list_anh_paths, 
            total_videos=video_count, 
            images_per_video=images_per_video
        )

        if count > 0:
            return f"""
            <h2>🎉 Hoàn thành!</h2>
            <p>Đã tạo thành công <strong>{count}/{video_count}</strong> video.</p>
            <p>📁 Kiểm tra thư mục: <code>videos_capcut</code></p>
            <a href="/">← Tạo thêm video</a>
            """, 200
        else:
            return "❌ Không tạo được video nào. Xem log terminal để biết chi tiết.", 500

    except Exception as e:
        return f"Lỗi hệ thống: {str(e)}", 500


if __name__ == '__main__':
    app.run(port=5001, debug=True)