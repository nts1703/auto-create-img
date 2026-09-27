import os
import time
import base64
import requests
import datetime
import random  # Thêm để random prompt
from flask import Flask, render_template, request
from playwright.sync_api import sync_playwright

# ==========================================
# CẤU HÌNH FLASK SERVER & ĐƯỜNG DẪN LƯU FILE
# ==========================================
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DOWNLOAD_FOLDER'] = 'downloads'
app.config['VIDEO_DOWNLOAD_FOLDER'] = 'downloads_video'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['VIDEO_DOWNLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('indrx1.html')

@app.route('/process', methods=['POST'])
def process():
    if 'image' not in request.files:
        return "Không tìm thấy file tải lên", 400
    
    file = request.files['image']
    if file.filename == '':
        return "Chưa chọn file", 400
        
    input_image_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(input_image_path)

    try:
        run_automation(os.path.abspath(input_image_path))
        return "Quy trình đang chạy! Đang tạo 5 video với prompt ngẫu nhiên. Vui lòng kiểm tra cửa sổ trình duyệt."
        
    except Exception as e:
        return f"Có lỗi xảy ra: {str(e)}", 500

# ==========================================
# DANH SÁCH 10 PROMPT KHÁC NHAU
# ==========================================
VIDEO_PROMPTS = [
    # Cầm đth trước gương
    "The woman in the original photo is gently using both hands to adjust her dress/ blouse with elegant fingers, she has a soft closed-mouth smile without showing teeth, warm and gentle facial expression, she slowly turns her body gracefully only 10 to 15 degrees to her right, minimal and natural movement, very smooth cinematic motion, soft lighting, realistic physics, high detail, 4K",
    "Make a realistic mirror selfie video. The girl continuously holds her phone while facing the mirror. Camera angle and framing stay nearly unchanged with no zoom. She looks at herself, slowly makes a cute pout, smiles afterward, slightly raises her eyebrows, and gently shifts her weight. Small natural movements only. Photorealistic, stable composition.",
    "Make a realistic mirror selfie video. The girl keeps holding her phone with one hand and briefly raises her other hand beside her face to make a peace sign (V sign). Camera remains almost perfectly still with no zoom or major framing changes. She smiles naturally, blinks, slightly tilts her head, then lowers her hand. Smooth realistic motion.",
    "Make a beautiful woman in the photo softly adjusting the fabric of her dress or top with delicate hand movements, gentle closed-mouth smile with soft lips, serene and elegant expression, slowly turning her upper body gracefully about 10-15 degrees, subtle and natural motion, very smooth cinematic movement, soft flattering lighting, realistic fabric physics, highly detailed, 4K video",
    "Make a realistic mirror selfie video. The girl continues holding her phone in front of the mirror the entire time. Camera angle stays almost identical with no zoom or noticeable movement. She first admires herself in the mirror, then gives a gentle smile, briefly makes a small pout, flashes a peace sign, finishes with a finger heart gesture, and returns to a relaxed pose. All movements are slow, subtle, and natural. Photorealistic, stable framing.",
    "Make a realistic mirror selfie video. The girl continuously holds her phone while facing the mirror. Camera framing stays almost perfectly fixed with no zoom or noticeable camera movement. She gently tucks a strand of hair behind her ear with her free hand, lightly smiles at her reflection, blinks naturally, and slightly tilts her head before returning to a relaxed pose. Smooth, realistic motion and natural lighting.",
    "Make a realistic mirror selfie video. The girl keeps holding her phone throughout the entire clip. Camera angle and framing remain nearly identical with no zoom or camera movement. She looks at herself in the mirror, lets out a silent giggle, briefly covers the corner of her mouth with her free hand, smiles brightly, then relaxes while maintaining eye contact with her reflection. Natural breathing, subtle body movement, photorealistic.",
    "Make a realistic mirror selfie video. The girl holds her phone in front of the mirror during the entire clip. Camera remains stable with almost no change in framing and absolutely no zoom. She gently adjusts the collar of her shirt with her free hand, gives herself an approving smile in the mirror, slightly nods, blinks naturally, and returns to a relaxed standing pose. Smooth, subtle, realistic movement with consistent lighting."

    # Review son
    # "Tạo cho tôi video về người này đang review son, cô ấy thoa 1 chút son lên môi mà mím môi nhẹ, sau đó lắc lắc thỏi son và cười mỉm, lưu ý không cười lộ răng, độ nét 4k, ánh sáng tốt, camera mượt mà, hành động tự nhiên.",
    # "Make A beautiful young woman applying the pink lip gloss directly onto her lips with the applicator, focus on the glossy texture and shimmer, natural lighting, smooth camera movement focusing on the lips and face, realistic skin texture, highly detailed, 4k.Remember to smile without showing her teeth.",
    # "make a video: Close-up of a young woman with a natural makeup look, holding a pink lip gloss, opening the product, swatching the gloss on the back of her hand, expressive facial emotions, high quality, soft studio lighting, cinematic, 4k.Remember to smile without showing her teeth.",
    # "make Split screen video, one side shows bare lips, the other side shows the young woman applying the pink lip gloss, vibrant color transition, she smiles confidently to the camera, high definition, professional beauty vlog aesthetic, 4k.Remember to smile without showing her teeth.",
    # "make video A young woman getting ready in a cozy room, applying the pink lip gloss while looking into a mirror, natural soft sunlight, relaxed atmosphere, candid shots, high resolution, realistic textures, 4k.Remember to smile without showing her teeth.",
    # "make video Macro shot of the pink lip gloss bottle, hand opening the cap, showing the liquid texture, then shifting focus to the woman's face as she applies it, bokeh background, elegant and clean beauty advertisement style, 4k.Remember to smile without showing her teeth."
    
]

# ==========================================
# CẤU HÌNH PLAYWRIGHT (BOT AUTOMATION)
# ==========================================
def run_automation(input_image_path):
    user_data_dir = os.path.join(os.getcwd(), "browser_data")
    
    # Tạo mã thời gian độc nhất
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        page = browser.new_page()

        # ------------------------------------------
        # BƯỚC 1: XỬ LÝ TRÊN GEMINI
        # ------------------------------------------
        print("\n--- [BƯỚC 1] BẮT ĐẦU XỬ LÝ TRÊN GEMINI ---")
        print("Đang truy cập Gemini...")
        page.goto("https://gemini.google.com/")
        page.wait_for_load_state("domcontentloaded")
        
        print("Đang chờ ô nhập liệu xuất hiện...")
        page.wait_for_selector('div[aria-label*="Gemini"]', timeout=45000)
        time.sleep(2)

        print("Đang tiến hành tải ảnh lên Gemini...")
        try:
            page.set_input_files('input[type="file"]', input_image_path, timeout=3000)
        except Exception:
            print("Không nạp thẳng được, tiến hành mở Menu dấu (+)...")
            trigger_btn = page.locator('button[aria-label="Nội dung tải lên và công cụ"]')
            trigger_btn.wait_for(state="visible", timeout=10000)
            trigger_btn.click()
            time.sleep(1.5) 
            
            gemini_upload_btn = page.locator('button[data-test-id="local-images-files-uploader-button"]')
            with page.expect_file_chooser() as fc_info:
                gemini_upload_btn.click(force=True)
            file_chooser = fc_info.value
            file_chooser.set_files(input_image_path)
            
        print("Đang chờ ảnh hiển thị trên khung chat...")
        time.sleep(3) 
        
        print("Đang nhập câu lệnh (Prompt)...")
        #Cầm đth đứng trước gương
        # page.locator('div[aria-label*="Gemini"]').fill("Giữ nguyên hoàn toàn background, ánh sáng, nội thất, phong cách ảnh gốc. đứng/ngồi (phụ thuộc vào ảnh tôi gửi) tự chụp ảnh trước gương (selfie trước gương) bằng điện thoại di động để tạo dáng và khoe trang phục (outfit). Người trong ảnh không cầm điện thoại lên cao kiểu selfie, có thể để điện thoại ở tay dưới. Giữ nguyên ngoại hình, tóc, trang phục, dáng người và chi tiết khuôn mặt. Đảm bảo người trong ảnh không bị lỗi bộ phận cơ thể, không bị biến dạng, không bị cắt cụt. Tạo ảnh chân thực, sắc nét, chất lượng cao, độ phân giải cao. Không thêm bất kỳ chi tiết nào khác ngoài người trong ảnh và background gốc.")
        
        #tăng độ nét
        page.locator('div[aria-label*="Gemini"]').fill("A 4K, ultra-high-resolution photograph of the scene depicted in the picture, maintaining the exact original composition, subjects, lighting, and all specific details. Apply professional AI upscaling, intricate texture enhancement, and advanced detail reconstruction to achieve maximum sharpness and clarity, while preserving the original authenticity and every element of the image. Eliminate any blur or noise. The final image must be an exact high-definition replica of the source material.")
        
        time.sleep(1)
        
        print("Đang nhấn nút Gửi...")
        page.locator('button[aria-label*="Gửi tin nhắn"], button[aria-label*="Send"]').click()
        
        print("Đang chờ Gemini tạo ảnh...")
        time.sleep(10) 
        
        # ĐỔI TÊN: File ảnh được gắn thêm timestamp
        downloaded_image_path = os.path.abspath(os.path.join(app.config['DOWNLOAD_FOLDER'], f"gemini_{timestamp}.png"))
        image_captured = False
        timeout = 300
        start_time = time.time()
        
        print("Đang quét trích xuất ảnh kết quả...")
        while time.time() - start_time < timeout:
            img_elements = page.locator('model-response img, .model-response img').all()
            if not img_elements:
                img_elements = page.locator('img').all()
                
            for img in reversed(img_elements):
                try:
                    class_attr = img.get_attribute('class') or ''
                    src_attr = img.get_attribute('src') or ''
                    
                    if any(k in class_attr.lower() or k in src_attr.lower() for k in ['avatar', 'account', 'profile', 'icon', 'logo', 'mavatar']):
                        continue
                        
                    img_handle = img.element_handle()
                    
                    result = page.evaluate("""
                        (img) => {
                            if (!img || !img.complete || img.naturalWidth === 0) return null;
                            if (img.closest('user-query') || img.closest('.query-text') || img.closest('.message-content-user')) {
                                return { status: 'is_input_prompt_image' };
                            }
                            if (img.naturalWidth < 300 || img.naturalHeight < 300) {
                                return { status: 'too_small' };
                            }
                            const canvas = document.createElement('canvas');
                            canvas.width = img.naturalWidth;
                            canvas.height = img.naturalHeight;
                            const ctx = canvas.getContext('2d');
                            ctx.drawImage(img, 0, 0);
                            return { status: 'success', data: canvas.toDataURL('image/png') };
                        }
                    """, img_handle)
                    
                    if result and result['status'] == 'success':
                        base64_data = result['data']
                        img_bytes = base64.b64decode(base64_data.split(",")[1])
                        with open(downloaded_image_path, "wb") as f:
                            f.write(img_bytes)
                        image_captured = True
                        break
                except Exception:
                    continue
            if image_captured:
                break 
            time.sleep(3)
            
        if not image_captured:
            raise Exception("Quá thời gian quy định nhưng không thể lấy được ảnh kết quả từ Gemini.")
            
        print(f"Đã lưu ảnh Gemini tại: {downloaded_image_path}")

        # ------------------------------------------
        # BƯỚC 2: XỬ LÝ TRÊN META AI - TẠO 5 VIDEO VỚI PROMPT RANDOM
        # ------------------------------------------
        print("\n--- [BƯỚC 2] BẮT ĐẦU TẠO 5 VIDEO TRÊN META AI ---")

        selected_prompts = random.sample(VIDEO_PROMPTS, 5)

        for i in range(1, 6):
            current_prompt = selected_prompts[i-1]
            print(f"\n📹 Đang tạo video thứ {i}/5...")
            print(f"Prompt đang dùng: {current_prompt[:100]}...")

            # Tải lại trang Meta AI
            page.goto("https://www.meta.ai/")
            page.wait_for_load_state("domcontentloaded")
            time.sleep(3)

            # ===== XỬ LÝ TRƯỜNG HỢP BỊ REDIRECT SANG ĐĂNG NHẬP =====
            current_url = page.url
            if "auth.meta.com" in current_url or "login" in current_url.lower():
                print("⚠️  Phát hiện trang đăng nhập Meta.")
                print("👉 Vui lòng đăng nhập thủ công trong cửa sổ trình duyệt.")
                print("   Script sẽ đợi tối đa 5 phút cho đến khi bạn đăng nhập xong...")

                # Đợi tối đa 5 phút cho đến khi composer xuất hiện (nghĩa là đã login thành công)
                try:
                    page.wait_for_selector(
                        'div[data-testid="composer-input"]',
                        timeout=300000  # 5 phút
                    )
                    print("✅ Đã đăng nhập thành công!")
                except Exception:
                    raise Exception("Timeout: Bạn chưa đăng nhập xong trong 5 phút. Vui lòng chạy lại và đăng nhập nhanh hơn.")
            else:
                # Đã ở trang chính → chờ composer bình thường
                page.wait_for_selector('div[data-testid="composer-input"]', timeout=30000)

            time.sleep(2)

            # ===== PHẦN UPLOAD ẢNH (giữ nguyên logic cũ của bạn) =====
            print(f"Đang upload ảnh lần {i}...")
            try:
                page.set_input_files('input[type="file"].hidden', downloaded_image_path)
            except Exception:
                print("Fallback upload...")
                # Thử các selector upload phổ biến hơn
                upload_selectors = [
                    'button[aria-label*="Upload"]',
                    'button[aria-label*="Tải lên"]',
                    'button[data-testid*="upload"]',
                    'input[type="file"]'
                ]
                uploaded = False
                for sel in upload_selectors:
                    try:
                        if page.locator(sel).count() > 0:
                            with page.expect_file_chooser() as fc_info:
                                page.locator(sel).first.click(force=True)
                            fc_info.value.set_files(downloaded_image_path)
                            uploaded = True
                            break
                    except:
                        continue
                if not uploaded:
                    print("⚠️  Không tìm thấy nút upload. Bạn có thể upload thủ công.")
                    time.sleep(8)  # cho bạn thời gian upload tay

            time.sleep(3)

            # Kích hoạt nút Tạo video (giữ nguyên)
            video_btn = page.locator('button[data-slot="capability-pill"]:has-text("Tạo video")')
            if video_btn.is_visible():
                is_selected = video_btn.get_attribute("data-selected")
                if is_selected == "false":
                    print("Nút 'Tạo video' chưa được chọn. Tiến hành click kích hoạt...")
                    video_btn.click()
                    time.sleep(1)

            # Nhập prompt + gửi (giữ nguyên)
            print("Đang điền Prompt tạo video vào ô chat...")
            page.locator('div[data-testid="composer-input"]').fill(current_prompt)
            time.sleep(1)

            print("Đang nhấn nút Gửi...")
            page.locator('button[data-testid="composer-send-button"]').click()

            # Phần chờ video (giữ nguyên logic của bạn)
            # ... (phần còn lại không cần sửa)
            
            # ====================== PHẦN CHỜ VIDEO ĐÃ ĐƯỢC CẢI TIẾN ======================
            print(f"Đang chờ Meta AI tạo video {i}/5... (tối đa 2 phút)")
            
            video_downloaded = False
            max_wait_seconds = 120  # 2 phút
            check_interval = 8
            
            start_time = time.time()
            
            while (time.time() - start_time) < max_wait_seconds:
                try:
                    # Kiểm tra xem có video chưa
                    video_element = page.locator('video').last
                    if video_element.is_visible():
                        print("✅ Đã phát hiện thấy Video kết quả!")
                        video_downloaded = True
                        break
                except:
                    pass
                
                time.sleep(check_interval)
                
                # Nếu đã chờ hơn 90 giây mà chưa có video → tự động gửi nhắc
                if (time.time() - start_time) > 90 and not video_downloaded:
                    try:
                        print("⏳ Chờ lâu, tự động gửi nhắc: 'gửi video cho tôi'...")
                        page.locator('div[data-testid="composer-input"]').fill("gửi video cho tôi")
                        page.locator('button[data-testid="composer-send-button"]').click()
                        time.sleep(5)  # chờ Meta AI phản hồi
                    except:
                        pass
            
            # ====================== XỬ LÝ SAU KHI CHỜ ======================
            if video_downloaded:
                print("Đang bóc tách dữ liệu video...")
                video_locator = page.locator('video').last
                video_handle = video_locator.element_handle()
                
                downloaded_video_path = os.path.abspath(
                    os.path.join(app.config['VIDEO_DOWNLOAD_FOLDER'], f"meta_{timestamp}_{i}.mp4")
                )
                
                # Thử lấy base64
                base64_video = page.evaluate("""
                    async (video) => {
                        if (!video || !video.src) return null;
                        try {
                            const response = await fetch(video.src);
                            const blob = await response.blob();
                            return new Promise((resolve) => {
                                const reader = new FileReader();
                                reader.onloadend = () => resolve(reader.result);
                                reader.readAsDataURL(blob);
                            });
                        } catch (e) {
                            return null;
                        }
                    }
                """, video_handle)
                
                if base64_video and "base64," in base64_video:
                    video_bytes = base64.b64decode(base64_video.split(",")[1])
                    with open(downloaded_video_path, "wb") as f:
                        f.write(video_bytes)
                    print(f"[THÀNH CÔNG] Video {i}/5 đã được lưu: {downloaded_video_path}")
                else:
                    # Fallback tải qua src
                    video_src = video_locator.get_attribute('src')
                    if video_src and not video_src.startswith('blob:'):
                        r = requests.get(video_src, stream=True)
                        with open(downloaded_video_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=1024*1024):
                                if chunk: f.write(chunk)
                        print(f"[THÀNH CÔNG DỰ PHÒNG] Video {i}/5 đã được lưu: {downloaded_video_path}")
                    else:
                        print(f"[CẢNH BÁO] Không thể trích xuất video {i}, nhưng đã thấy element.")
            else:
                print(f"[LỖI] Không tạo được video {i}/5 sau khi chờ và nhắc nhở.")
                print("   → Tiếp tục tạo video tiếp theo...")

        print("\n🎉 Quy trình tự động hoàn tất! Đã tạo 5 video với prompt khác nhau.")
        time.sleep(5)
        browser.close()

if __name__ == '__main__':
    app.run(debug=True)