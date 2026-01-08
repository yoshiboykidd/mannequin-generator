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

def get_safe_filename(name):
    mapping = {
        "真正面 (Front)": "Front",
        "斜め前 (Quarter)": "Quarter",
        "下から (Low Angle)": "Low",
        "斜め上から (High Angle)": "High"
    }
    return mapping.get(name, "mannequin_pose")

def get_b64_json_list(image_list):
    js_data = []
    for name, data in image_list:
        safe_name = get_safe_filename(name)
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
    .stDownloadButton button { background-color: #f0f2f6; color: #31333F; height: 2.5em !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🤖 マネキンポーズ一括生成 (身体のみ・台座除去)")

try:
    api_key = st.secrets["GOOGLE_API_KEY"]
except KeyError:
    st.error("Secretsに GOOGLE_API_KEY が設定されていません。")
    st.stop()

genai.configure(api_key=api_key)
MODEL_NAME = 'gemini-3-pro-image-preview'
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
        if st.button("4アングル一括生成を開始", type="primary"):
            st.session_state.start_gen = True

# ==========================================
# 4. 生成ロジック
# ==========================================

if uploaded_file and st.session_state.get('start_gen'):
    st.session_state.generated_images = []
    angles = {
        "真正面 (Front)": "Viewed directly from the straight-on front perspective.",
        "斜め前 (Quarter)": "Viewed from a standard 45-degree three-quarter angle.",
        "下から (Low Angle)": "A dynamic low-angle shot from below (worm's-eye view).",
        "斜め上から (High Angle)": "A high-angle shot from diagonally above (bird's-eye view)."
    }
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_angles = len(angles)
    
    for i, (angle_key, angle_desc) in enumerate(angles.items()):
        status_text.write(f"🔄 生成中 ({i+1}/{total_angles}): {angle_key}...")
        
        # === 台座を除去するための強力なプロンプトに変更 ===
        prompt = f"""
        [Task: Pure Body Extraction]
        Transform the subject in the reference image into a neutral grey plastic mannequin.
        
        - Pose: Replicate the anatomical pose of the person/subject exactly.
        - Perspective: {angle_desc}
        - EXCLUDE: COMPLETELY REMOVE all pedestals, bases, supports, chairs, props, and floors from the reference image.
        - Result: Generate ONLY the mannequin's body. The mannequin should be standing or floating in a void or on a plain flat floor.
        - Detail: Smooth matte texture, no hair, no facial features, no clothes.
        - Background: Solid plain white background only.
        - Composition: Full body, vertical 2:3 aspect ratio.
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
            progress_bar.progress((i + 1) / total_angles)
            time.sleep(0.5)
        except Exception as e:
            st.error(f"{angle_key} の生成に失敗しました: {e}")
    
    status_text.success(f"✅ 台座除去版の生成が完了しました！")
    st.session_state.start_gen = False

# ==========================================
# 5. 表示と保存機能
# ==========================================

if st.session_state.generated_images:
    st.divider()
    cols = st.columns(4)
    for idx, (name, data) in enumerate(st.session_state.generated_images):
        with cols[idx]:
            st.subheader(name)
            st.image(data, use_container_width=True)
            safe_fn = get_safe_filename(name)
            st.download_button(label=f"保存: {name}", data=data, file_name=f"mannequin_{safe_fn}.jpg", mime="image/jpeg", key=f"btn_{idx}")

    st.divider()
    
    st.write("### 💾 一括保存")
    if st.button("4枚連続で保存ダイアログを開く", type="primary"):
        json_data = get_b64_json_list(st.session_state.generated_images)
        js_code = f"""
        <script>
            async function downloadAll() {{
                const files = {json_data};
                for (let i = 0; i < files.length; i++) {{
                    const file = files[i];
                    const a = document.createElement('a');
                    a.href = file.data;
                    a.download = file.name;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    await new Promise(resolve => setTimeout(resolve, 800));
                }}
            }}
            downloadAll();
        </script>
        """
        components.html(js_code, height=1)
        st.toast("一括保存を開始しました。")
