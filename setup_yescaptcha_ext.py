"""
下载并设置 YesCaptcha Chrome 扩展
"""
import os
import sys
import zipfile
import shutil

# YesCaptcha 扩展下载地址（CRX from Chrome Web Store）
# 使用 CRX Downloader service 获取
EXT_ID = "jiofmdifioeejeilfkpegipdjiopiekl"
EXT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yescaptcha_ext")

def download_extension():
    """Download YesCaptcha extension from Chrome Web Store."""
    import urllib.request

    if os.path.exists(EXT_DIR) and os.path.isfile(os.path.join(EXT_DIR, "manifest.json")):
        print(f"✅ 扩展已存在: {EXT_DIR}")
        return True

    print("📥 下载 YesCaptcha 扩展...")

    # Chrome Web Store CRX download URL
    crx_url = (
        f"https://clients2.google.com/service/update2/crx?"
        f"response=redirect&prodversion=125.0.0.0&acceptformat=crx2,crx3"
        f"&x=id%3D{EXT_ID}%26uc"
    )

    crx_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yescaptcha.crx")

    try:
        req = urllib.request.Request(crx_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            with open(crx_path, "wb") as f:
                f.write(resp.read())
        print(f"  ✅ 下载完成: {crx_path}")
    except Exception as e:
        print(f"  ❌ 下载失败: {e}")
        print(f"  请手动下载扩展:")
        print(f"  1. 打开 https://chrome.google.com/webstore/detail/{EXT_ID}")
        print(f"  2. 安装后在 chrome://extensions/ 找到扩展目录")
        print(f"  3. 复制整个扩展文件夹到: {EXT_DIR}")
        return False

    # Extract CRX (which is a ZIP with extra header)
    print("📦 解压扩展...")
    os.makedirs(EXT_DIR, exist_ok=True)

    try:
        # CRX3 format: skip the header
        with open(crx_path, "rb") as f:
            data = f.read()

        # Find PK zip signature
        zip_start = data.find(b'PK\x03\x04')
        if zip_start == -1:
            print("  ❌ CRX 格式无法识别")
            return False

        zip_path = crx_path + ".zip"
        with open(zip_path, "wb") as f:
            f.write(data[zip_start:])

        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(EXT_DIR)

        os.remove(crx_path)
        os.remove(zip_path)
        print(f"  ✅ 解压完成: {EXT_DIR}")
        return True

    except Exception as e:
        print(f"  ❌ 解压失败: {e}")
        return False


if __name__ == "__main__":
    success = download_extension()
    sys.exit(0 if success else 1)
