import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import base64
import streamlit.components.v1 as components
import time

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
        # ファイル名に使える文字だけにサニタイズ
        safe_name = name.replace(" ", "_").replace("(", "").replace(")", "")
        b64 = base64.b64encode(data).decode()
        js_data.append(f'{{ "data": "data:image/jpeg;base64,{b64}", "name": "mannequin_{safe_name}.jpg" }}')
    return "[" + ",".join(js_data) + "]"

# ==========================================
# 2. アプリ初期設定
# ==========================================

st.set_page_config(page_title="Multi-Angle Mannequin Gen", layout="wide")

st.markdown("""
    <style>
    .stButton button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🤖 マネキンポーズ素材一括生成 (あおり/俯瞰対応)")
st.write("元の写真から「斜め前」「下から(あおり)」「斜め上から(俯瞰)」の3アングルを生成します。")

try:
    api_key = st.secrets["GOOGLE_API_KEY"]
except KeyError:
    st.error("Secretsに GOOGLE_API_KEY が設定されていません。")
    st.stop()

genai.configure(api_key=api_key)
MODEL_NAME = 'gemini-3-pro-image-preview' # Nano Banana Pro
model = genai.GenerativeModel(MODEL_NAME)

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
    st.session_state.generated_images = []
    
    # === ここが変更点：新しいアングル定義 ===
    angles = {
        "斜め前 (Quarter)": "Viewed from a standard 45-degree three-quarter angle.",
        "下から (Low Angle)": "A dynamic low-angle shot, viewing the mannequin from below (worm's-eye view), emphasizing its stature.",
        "斜め上から (High Angle)": "A high-angle shot, viewing the mannequin from diagonally above (bird's-eye view), looking down."
    }
    # =====================================
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, (angle_key, angle_desc) in enumerate(angles.items()):
        status_text.write(f"🔄 生成中 ({i+1}/3): {angle_key}...")
        
        prompt = f"""
        A high-quality studio photograph of a neutral grey plastic mannequin base body.
        Based on the pose in the reference image, depict the mannequin as {angle_desc}
        Replicate the limb geometry accurately from this perspective.
        No hair, no clothes, no facial features. 
        Smooth, matte surface, plain white background. Vertical 2:3 aspect ratio.
        """
        
        try:
            response = model.generate_content([prompt, input_image])
            
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
            time.sleep(0.5) # API負荷軽減のため少し待つ
            
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
    
    for idx, (name, data) in enumerate(st.session_state.generated_images):
        with cols[idx]:
            st.subheader(name)
            st.image(data, use_container_width=True)
            st.caption(f"1000x1500px / JPEG")

    st.divider()
    
    st.write("### 💾 保存オプション")
    if st.button("指定フォルダへ3枚まとめて保存 (連続ダイアログ起動)", type="primary"):
        json_data = get_b64_json_list(st.session_state.generated_images)
        
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
