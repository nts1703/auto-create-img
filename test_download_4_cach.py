import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# ==================== CẤU HÌNH ====================
PROFILE = "browser_data_6"
OUTPUT_FOLDER = "test_download_results"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Selector nút Share trên ảnh (cách A)
SHARE_ON_IMAGE = (
    'button[aria-label="Chia sẻ hình ảnh này"], '
    'button[aria-label*="Chia sẻ hình ảnh"], '
    'button[aria-label*="Share this image"]'
)

# Selector nút Share dưới tin nhắn (cách B)
SHARE_IN_ACTIONS = 'button[aria-label="Chia sẻ"], button[aria-label*="Share"]:not([aria-label*="hình ảnh"])'

# Selector nút Download trực tiếp (cách D)
DOWNLOAD_DIRECT = (
    'button[aria-label*="Download"], button[aria-label*="Tải xuống"], '
    'button:has-text("Tải xuống"), button:has-text("Download")'
)

# Selector nút Tải xuống trong menu (dùng chung cho A và B)
DOWNLOAD_IN_MENU = (
    'button.interactive-button:has-text("Tải xuống"), '
    'button:has-text("Tải xuống"), '
    'button:has-text("Download"), '
    'div[role="menuitem"]:has-text("Tải xuống")'
)


def save_download(download, method_name):
    """Lưu file tải về với tên theo cách thành công"""
    timestamp = datetime.now().strftime("%H%M%S")
    file_name = f"Cach{method_name}_{timestamp}.png"
    save_path = os.path.join(OUTPUT_FOLDER, file_name)
    download.save_as(save_path)
    print(f"   💾✅ ĐÃ LƯU THÀNH CÔNG bằng CÁCH {method_name}: {save_path}")
    return True


def try_method_A(page):
    """Cách A: Click nút Share trên ảnh → Tải xuống"""
    print("\n--- Đang thử CÁCH A: Share trên ảnh → Tải xuống ---")
    try:
        share_btn = page.locator(SHARE_ON_IMAGE).last
        if not share_btn.is_visible(timeout=5000):
            print("   ❌ Cách A: Không thấy nút Share trên ảnh")
            return False

        print("   📤 Cách A: Đã thấy nút Share trên ảnh, đang click...")
        share_btn.click(force=True)
        page.wait_for_timeout(1500)

        download_btn = page.locator(DOWNLOAD_IN_MENU).last
        if not download_btn.is_visible(timeout=6000):
            print("   ❌ Cách A: Không thấy nút Tải xuống trong menu")
            try:
                page.keyboard.press("Escape")
            except:
                pass
            return False

        print("   📥 Cách A: Đang click Tải xuống (dùng JS click)...")
        with page.expect_download(timeout=15000) as download_info:
            download_btn.evaluate("el => el.click()")

        download = download_info.value
        save_download(download, "A")

        try:
            page.keyboard.press("Escape")
        except:
            pass
        return True

    except Exception as e:
        print(f"   ❌ Cách A thất bại: {e}")
        try:
            page.keyboard.press("Escape")
        except:
            pass
        return False


def try_method_B(page):
    """Cách B: Click nút Share dưới tin nhắn → Tải xuống"""
    print("\n--- Đang thử CÁCH B: Share dưới tin nhắn → Tải xuống ---")
    try:
        share_btn = page.locator(SHARE_IN_ACTIONS).last
        if not share_btn.is_visible(timeout=5000):
            print("   ❌ Cách B: Không thấy nút Share dưới tin nhắn")
            return False

        print("   📤 Cách B: Đã thấy nút Share dưới tin nhắn, đang click...")
        share_btn.click(force=True)
        page.wait_for_timeout(1500)

        download_btn = page.locator(DOWNLOAD_IN_MENU).last
        if not download_btn.is_visible(timeout=6000):
            print("   ❌ Cách B: Không thấy nút Tải xuống trong menu")
            try:
                page.keyboard.press("Escape")
            except:
                pass
            return False

        print("   📥 Cách B: Đang click Tải xuống (dùng JS click)...")
        with page.expect_download(timeout=15000) as download_info:
            download_btn.evaluate("el => el.click()")

        download = download_info.value
        save_download(download, "B")

        try:
            page.keyboard.press("Escape")
        except:
            pass
        return True

    except Exception as e:
        print(f"   ❌ Cách B thất bại: {e}")
        try:
            page.keyboard.press("Escape")
        except:
            pass
        return False


def try_method_C(page):
    """Cách C: Lấy src của ảnh generated rồi tải bằng request"""
    print("\n--- Đang thử CÁCH C: Lấy src ảnh rồi download ---")
    try:
        last_assistant = page.locator('article, div[data-message-author-role="assistant"]').last
        imgs = last_assistant.locator("img")
        count = imgs.count()

        if count == 0:
            print("   ❌ Cách C: Không tìm thấy thẻ img nào")
            return False

        img = imgs.last
        src = img.get_attribute("src")

        if not src:
            print("   ❌ Cách C: Không lấy được src")
            return False

        print(f"   🔗 Cách C: Tìm thấy src: {src[:80]}...")

        if src.startswith("blob:"):
            print("   ⚠️ Cách C: src là blob: → không tải được bằng request")
            return False

        response = page.request.get(src)
        if response.status != 200:
            print(f"   ❌ Cách C: Request thất bại, status = {response.status}")
            return False

        timestamp = datetime.now().strftime("%H%M%S")
        file_name = f"CachC_{timestamp}.png"
        save_path = os.path.join(OUTPUT_FOLDER, file_name)

        with open(save_path, "wb") as f:
            f.write(response.body())

        print(f"   💾✅ ĐÃ LƯU THÀNH CÔNG bằng CÁCH C: {save_path}")
        return True

    except Exception as e:
        print(f"   ❌ Cách C thất bại: {e}")
        return False


def try_method_D(page):
    """Cách D: Click nút Download trực tiếp (nếu có)"""
    print("\n--- Đang thử CÁCH D: Nút Download trực tiếp ---")
    try:
        download_btn = page.locator(DOWNLOAD_DIRECT).last
        if not download_btn.is_visible(timeout=5000):
            print("   ❌ Cách D: Không thấy nút Download trực tiếp")
            return False

        print("   📥 Cách D: Đã thấy nút Download, đang click...")
        with page.expect_download(timeout=15000) as download_info:
            download_btn.evaluate("el => el.click()")

        download = download_info.value
        save_download(download, "D")
        return True

    except Exception as e:
        print(f"   ❌ Cách D thất bại: {e}")
        return False


def main():
    print("=" * 60)
    print("🧪 TEST TẢI ẢNH GPT - 4 CÁCH")
    print("=" * 60)
    print(f"Profile: {PROFILE}")
    print(f"Thư mục lưu: {OUTPUT_FOLDER}")
    print("-" * 60)
    print("Hướng dẫn:")
    print("1. Browser sẽ mở ChatGPT (profile 6)")
    print("2. Bạn TỰ upload ảnh + nhập prompt để GPT sinh ảnh")
    print("3. Khi ảnh xuất hiện, tool sẽ tự nhận biết và thử tải")
    print("-" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page()

        print("🌐 Đang mở ChatGPT...")
        page.goto("https://chatgpt.com/")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(5)

        print("\n✅ Browser đã sẵn sàng!")
        print("👉 Bây giờ bạn hãy tự upload ảnh + nhập prompt để GPT sinh ảnh.")
        print("👉 Tool đang lắng nghe nút Share trên ảnh...\n")

        try:
            page.wait_for_selector(
                SHARE_ON_IMAGE,
                state="visible",
                timeout=0
            )
            print("\n" + "=" * 60)
            print("🎉 Phát hiện gpt sinh ảnh mới")
            print("=" * 60)

            page.wait_for_timeout(2000)

            methods = [
                ("A", try_method_A),
                ("B", try_method_B),
                ("C", try_method_C),
                ("D", try_method_D),
            ]

            success = False
            for name, func in methods:
                start = time.time()
                ok = func(page)
                elapsed = time.time() - start

                if ok:
                    success = True
                    print(f"\n✅ CÁCH {name} THÀNH CÔNG (mất {elapsed:.1f}s)")
                    break
                else:
                    print(f"\n❌ CÁCH {name} THẤT BẠI (sau {elapsed:.1f}s) → chuyển sang cách tiếp theo")
                    try:
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(500)
                    except:
                        pass

            if not success:
                print("\n" + "=" * 60)
                print("⚠️ TẤT CẢ 4 CÁCH ĐỀU THẤT BẠI")
                print("=" * 60)
            else:
                print("\n" + "=" * 60)
                print("🎉 ĐÃ TẢI ẢNH THÀNH CÔNG")
                print("=" * 60)

        except KeyboardInterrupt:
            print("\n🛑 Đã dừng bởi người dùng")

        print("\n👉 Bạn có thể đóng browser hoặc nhấn Ctrl+C để thoát.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Thoát test.")
            browser.close()


if __name__ == "__main__":
    main()