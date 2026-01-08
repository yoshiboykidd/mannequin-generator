import streamlit as st
import google.generativeai as genai
from PIL import Image
import io

# ==========================================
# 1. 画像処理関数（2:3比率 / 1000px / 300kb制限）
# ==========================================
def process_and_compress_image(img, target_width=1000, max_kb=300):
    # 2:3の比率に強制リサイズ (1000px x 1500px)
    target_height = int(target_width * 1.5)
    img = img.resize((target_width, target_height), Image.LANCZOS)
    
    # 300kb以下になるまで画質(quality)を下げていく
    quality = 95
    while True:
        buf = io.BytesIO()
        # マネキン素体なのでJPEGで保存
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        size_kb = len(buf.getvalue()) / 1024
        if size_kb <= max_kb or quality <= 10:
            break
        quality -= 5  # 5ずつ画質を落とす
    
    return buf.getvalue(), size_kb, quality

# ==========================================
# 2. 初期設定
# ==========================================
st.set_page_config(page_title="Mannequin Pose Gen", layout="centered")
st.title("🤖 マネキンポーズ素材生成")
st.write("設定: 2:3比率 / 横1000px / 300kb以下")

# APIキー取得
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
except KeyError:
    st.error("Secretsに GOOGLE_API_KEY が設定されていません。")
    st.stop()

genai.configure(api_key=api_key)

# モデル名（着せ替えツールと同じ最新プレビュー版）
MODEL_NAME = 'gemini-3-pro-image-preview'
model = genai.GenerativeModel(MODEL_NAME)

# ==========================================
# 3. メインUI
# ==========================================
uploaded_file = st.file_uploader("ポーズの元写真をアップロード", type=["jpg", "png", "jpeg"])

if uploaded_file:
    input_image = Image.open(uploaded_file)
    st.image(input_image, caption="元画像", use_container_width=True)

    if st.button("マネキン素材を生成", type="primary"):
        with st.spinner('AIが生成中... (Nano Banana Pro実行中)'):
            # プロンプト
            prompt = """
            A high-quality studio photograph of a neutral grey plastic mannequin.
            Strictly replicate the exact pose and body orientation of the person in the image.
            No hair, no clothes, no facial features. 
            Smooth, matte surface, plain white background. Vertical 2:3 aspect ratio.
            """

            try:
                # 画像生成の実行
                response = model.generate_content([prompt, input_image])

                # 画像データの取り出し
                image_data = None
                if hasattr(response, 'parts'):
                    for part in response.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            image_data = part.inline_data.data
                            break
                
                if image_data:
                    generated_img = Image.open(io.BytesIO(image_data))
                    
                    # --- 画像の後処理（1000px/2:3/300kb） ---
                    final_bytes, final_size, final_quality = process_and_compress_image(generated_img)
                    
                    st.success(f"生成完了！ ({final_size:.1f}kb / 縦横比 2:3)")
                    st.image(final_bytes, caption="生成されたマネキン素材", use_container_width=True)
                    
                    # ダウンロードボタン
                    st.download_button(
                        label="ポーズ素材をダウンロード",
                        data=final_bytes,
                        file_name="mannequin_pose.jpg",
                        mime="image/jpeg"
                    )
                else:
                    st.error("画像データがレスポンスに含まれていませんでした。")
                    if hasattr(response, 'text'):
                        st.info(f"AIの応答: {response.text}")

            except Exception as e:
                # ここが不足していた「except」ブロックです
                st.error(f"生成中にエラーが発生しました: {e}")
                st.info("モデル名が正しいか、APIの制限に達していないか確認してください。")
