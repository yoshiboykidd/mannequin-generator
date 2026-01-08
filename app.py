import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import base64
import streamlit.components.v1 as components

# ==========================================
# 1. 画像処理・ユーティリティ関数
# ==========================================

def process_and_compress_image(img, target_width=1000, max_kb=300):
    """2:3比率にリサイズし、300kb以下に圧縮する"""
    target_height = int(target_width * 1.5)
    img = img.resize((target_width, target_height), Image.LANCZOS)
    
    quality = 95
    while True:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        size_kb = len(buf.getvalue()) / 1024
        if size_kb <= max_kb or quality <= 10:
            break
        quality -= 5
    return buf.getvalue(), size_kb

def get_b64_json_list(image_list):
    """JavaScriptに渡すためのBase64データリストを作成"""
    js_data = []
    for name, data in image_list:
        b64 = base64.b64encode(data).decode()
        js_data.append(f'{{ "data": "data:image/jpeg;base64,{b64}", "name": "{name}.jpg" }}')
    return "[" + ",".join(js_data) + "]"

# ==========================================
# 2. アプリ初期設定
# ==========================================

st.set_page_config(page_title="Multi-Angle Mannequin Gen", layout="wide")

# カスタムCSS: ボタンを目立たせる
st.markdown("""
    <style>
    .stButton button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    </style>
    """, unsafe_allow_view_runtime=True)

st.title("🤖 マネキンポーズ素材一括生成システム")
st.write("3アングル（正面・斜め・側面）を自動生成し、連続保存ダイアログを起動します。")

# APIキー取得
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
except KeyError:
    st.error("Secretsに GOOGLE_API_KEY が設定されていません。")
    st.stop()

genai.configure(api_key=api_key)
MODEL_NAME = 'gemini-3-pro-image-preview' # Nano Banana Pro
model = genai.GenerativeModel(MODEL_NAME)

# セッション状態の初期化（生成画像を保持するため）
if 'generated_images' not in st.session_state:
    st.session_state.generated_images = []

# ==========================================
# 3. メインUI（サイドバー）
# ==========================================

with st.sidebar:
    st.header("1. 写真をアップロード")
    uploaded_file = st.file_uploader("JPG/PNG形式", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        input_image = Image.open(uploaded_file)
        st.image(input_image, caption="元画像", use_container_width=True)
        if st.button("一括生成を開始", type="primary"):
            st.session_state.start_gen = True

# ==========================================
# 4. 生成ロジック
# ==========================================

if uploaded_file and st.session_state.get('start_gen'):
    st.session_state.generated_images = [] # リセット
    angles = {
        "Front": "Viewed directly from the front (0 degrees).",
        "Quarter": "Viewed from a 45-degree three-quarter angle.",
        "Side": "Viewed directly from the side profile (90 degrees)."
    }
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, (angle_key, angle_desc) in enumerate(angles.items()):
        status_text.write(f"🔄 生成中 ({i+1}/3): {angle_key} アングル...")
        
        prompt = f"""
        A high-quality studio photograph of a neutral grey plastic mannequin base body.
        Depict the mannequin {angle_desc} based on the pose in the reference image.
        Replicate the limb geometry accurately from this perspective.
        No hair, no clothes, no facial features. 
        Smooth, matte surface, plain white background. Vertical 2:3 aspect ratio.
        """
        
        try:
            response = model.generate_content([prompt, input_image])
            
            # 画像データ抽出
            img_bytes = None
            if hasattr(response, 'parts'):
                for part in response.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        img_bytes = part.inline_data.data
                        break
            
            if img_bytes:
                raw_img = Image.open(io.BytesIO(img_bytes))
                processed_bytes, size_kb = process_and_compress_image(raw_img)
                st.session_state.generated_images.append((angle_key, processed_bytes))
            
            progress_bar.progress((i + 1) / 3)
            
        except Exception as e:
            st.error(f"{angle_key} の生成に失敗しました: {e}")
    
    status_text.success("✅ 3枚すべての生成が完了しました！")
    st.session_state.start_gen = False

# ==========================================
# 5. 表示と保存機能
# ==========================================

if st.session_state.generated_images:
    st.divider()
    cols = st.columns(3)
    
    # プレビュー表示
    for idx, (name, data) in enumerate(st.session_state.generated_images):
        with cols[idx]:
            st.subheader(f"Angle: {name}")
            st.image(data, use_container_width=True)
            st.caption(f"1000x1500px / JPEG")

    st.divider()
    
    # 連続保存ボタン（JavaScript実行）
    st.write("### 💾 保存オプション")
    st.info("※初回実行時はブラウザの「複数ファイルのダウンロード許可」を求めるポップアップが出るので『許可』してください。")
    
    if st.button("指定フォルダへ3枚まとめて保存 (連続ダイアログ起動)", type="primary"):
        json_data = get_b64_json_list(st.session_state.generated_images)
        
        # JavaScript: 0.5秒おきにダウンロードをキックする
        js_code = f"""
        <script>
            const files = {json_data};
            files.forEach((file, index) => {{
                setTimeout(() => {{
                    const a = document.body.appendChild(document.createElement('a'));
                    a.href = file.data;
                    a.download = file.name;
                    a.click();
                    a.remove();
                }}, index * 600);
            }});
        </script>
        """
        components.html(js_code, height=0)
        st.balloons()
