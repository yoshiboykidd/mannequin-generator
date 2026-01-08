import streamlit as st
import google.generativeai as genai
from PIL import Image
import io

# ==========================================
# 設定
# ==========================================
st.set_page_config(page_title="Mannequin Pose Material Gen", layout="centered")
st.title("🤖 マネキンポーズ素材生成 (2:3 / 1000px)")

# APIキー設定（Secretsから取得）
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("Secretsに GOOGLE_API_KEY が設定されていません。")
    st.stop()

genai.configure(api_key=api_key)

# モデル名（着せ替えツールと同じもの）
MODEL_NAME = 'gemini-3-pro-image-preview'
model = genai.GenerativeModel(MODEL_NAME)

# --- 画像を300kb以下に圧縮する関数 ---
def process_and_compress_image(img, target_width=1000, max_kb=300):
    # 1. リサイズ (横1000pxに合わせ、2:3なので縦は1500px)
    target_height = int(target_width * 1.5)
    img = img.resize((target_width, target_height), Image.LANCZOS)
    
    # 2. 圧縮 (300kb以下になるまでクオリティを下げる)
    quality = 95
    while True:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        size_kb = len(buf.getvalue()) / 1024
        if size_kb <= max_kb or quality <= 10:
            break
        quality -= 5  # 5ずつ下げて再試行
    
    return buf.getvalue(), size_kb, quality

# ==========================================
# メイン画面
# ==========================================
uploaded_file = st.file_uploader("ポーズの元写真をアップロード", type=["jpg", "png", "jpeg"])

if uploaded_file:
    input_image = Image.open(uploaded_file)
    st.image(input_image, caption="元画像", use_container_width=True)

    if st.button("マネキン素材を生成", type="primary"):
        with st.spinner('生成中...'):
            # 強力なマネキン化プロンプト
            prompt = """
            A high-quality studio photograph of a neutral grey plastic mannequin.
            Strictly follow the exact pose and body orientation of the person in the image.
            No hair, no clothes, no facial features. 
            Smooth, matte surface, plain white background. 2:3 aspect ratio.
            """

            try:
                # Gemini 3 Pro Image (Nano Banana) の設定
                # image_configでアスペクト比と解像度（1K=約1024px）を指定
                generation_config = {
                    "image_config": {
                        "aspect_ratio": "2:3",
                        "image_size": "1K"
                    }
                }

                response = model.generate_content(
                    [prompt, input_image],
                    generation_config=generation_config
                )

                # レスポンスから画像データを取得
                image_data = None
                for part in response.parts:
                    if hasattr(part, 'inline_data'):
                        image_data = part.inline_data.data
                        break
                
                if image_data:
                    generated_img = Image.open(io.BytesIO(image_data))
                    
                    # --- 画像の後処理（リサイズ ＆ 300kb制限） ---
                    final_bytes, final_size, final_quality = process_and_compress_image(generated_img)
                    
                    st.success(f"生成完了！ (サイズ: {final_size:.1f}kb / Quality: {final_quality})")
                    st.image(final_bytes, caption="生成されたマネキン素材", use_container_width=True)
                    
                    # ダウンロード
                    st.download_button(
                        label="ポーズ素材をダウンロード",
                        data=final_bytes,
                        file_name="mannequin_pose.jpg",
                        mime="image/jpeg"
                    )
                else:
                    st.error("画像データが取得できませんでした。プロンプトやモデル設定を確認してください。")

            except Exception as e:
                st.error(f"エラー: {e}")
