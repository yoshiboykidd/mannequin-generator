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
    return buf.getvalue()

def get_safe_angle_name(name):
    mapping = {
        "真正面 (Front)": "Front",
        "斜め前 (Quarter)": "Quarter",
        "下から (Low Angle)": "Low",
        "斜め上から (High Angle)": "High"
    }
    return mapping.get(name, "pose")

def get_b64_json_list(image_dict, pose_id):
    js_data = []
    for name, data in image_dict.items():
        if data is None: continue
        angle_fn = get_safe_angle_name(name)
        filename = f"pose_{pose_id}_{angle_fn}.jpg"
        b64 = base64.b64encode(data).decode()
        js_data.append(f'{{ "data": "data:image/jpeg;base64,{b64}", "name": "{filename}" }}')
    return "[" + ",".join(js_data) + "]"

# ==========================================
# 2. アプリ初期設定
# ==========================================

st.set_page_config(page_title="Balanced Mannequin Gen", layout="wide")

st.markdown("""
    <style>
    .stButton button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    .stDownloadButton button { background-color: #f0f2f6; color: #31333F; height: 2.5em !important; }
    .regen-btn button { height: 2em !important; font-size: 0.8em !important; background-color: #fff1f1; border: 1px solid #ffcaca; }
    </style>
    """, unsafe_allow_html=True)

st.title("🤖 マネキンポーズ素材生成 (バランス調整版)")

try:
    api_key = st.secrets["GOOGLE_API_KEY"]
except KeyError:
    st.error("Secretsに GOOGLE_API_KEY が設定されていません。")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-3-pro-image-preview')

if 'gen_dict' not in st.session_state:
    st.session_state.gen_dict = {
        "真正面 (Front)": None,
        "斜め前 (Quarter)": None,
        "下から (Low Angle)": None,
        "斜め上から (High Angle)": None
    }

# --- アングル定義（マイルドに調整） ---
angles_info = {
    "真正面 (Front)": "Viewed directly from the straight-on front perspective.",
    "斜め前 (Quarter)": "Viewed from a standard 45-degree three-quarter angle, showing depth.",
    "下から (Low Angle)": "A dynamic low-angle shot viewing the mannequin from below, emphasizing stature.",
    "斜め上から (High Angle)": "A high-angle shot from diagonally above, looking down to show the overall posture."
}

# --- 生成実行関数（ポーズ参照指示を復活） ---
def run_generation(angle_key, angle_desc, input_img):
    prompt = f"""
    [Task: Generate Clean Base Mannequin from Reference Pose]
    
    **Instructions:**
    1. Analyze the anatomical pose in the provided reference image accurately.
    2. Generate a uniform LIGHT GREY plastic mannequin base body exactly matching that pose.
    
    **CRITICAL NEGATIVE CONSTRAINTS:**
    - NO HAIR. NO CLOTHES. NO FACIAL FEATURES. NO pedestals or bases.
    
    **Perspective & Environment:**
    - Perspective: {angle_desc}
    - Background: Solid, PURE WHITE (RGB 255,255,255).
    - Aspect Ratio: Vertical 2:3.
    """
    try:
        response = model.generate_content([prompt, input_img])
        img_bytes = None
        if hasattr(response, 'parts'):
            for part in response.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    img_bytes = part.inline_data.data
                    break
        if img_bytes:
            raw_img = Image.open(io.BytesIO(img_bytes))
            return process_and_compress_image(raw_img)
    except Exception as e:
        st.error(f"生成エラー ({angle_key}): {e}")
    return None

# ==========================================
# 3. UI（サイドバー）
# ==========================================

with st.sidebar:
    st.header("1. 保存設定")
    pose_id = st.text_input("ポーズ番号", value="01")
    
    st.divider()
    st.header("2. 写真をアップロード")
    uploaded_file = st.file_uploader("JPG/PNG形式", type=["jpg", "png", "jpeg"])
    
    if uploaded_file:
        input_image = Image.open(uploaded_file)
        st.image(input_image, caption="元画像", use_container_width=True)
        
        if st.button("4アングル一括生成", type="primary"):
            progress_bar = st.progress(0)
            for i, (k, v) in enumerate(angles_info.items()):
                with st.spinner(f"{k} を生成中..."):
                    st.session_state.gen_dict[k] = run_generation(k, v, input_image)
                progress_bar.progress((i + 1) / 4)
            st.success("一括生成完了！")

# ==========================================
# 4. 表示と個別操作
# ==========================================

if any(st.session_state.gen_dict.values()):
    st.divider()
    cols = st.columns(4)
    
    for idx, (name, data) in enumerate(st.session_state.gen_dict.items()):
        with cols[idx]:
            st.subheader(name)
            if data:
                st.image(data, use_container_width=True)
                
                angle_fn = get_safe_angle_name(name)
                fn = f"pose_{pose_id}_{angle_fn}.jpg"
                st.download_button(label=f"保存: {fn}", data=data, file_name=fn, mime="image/jpeg", key=f"dl_{idx}")
                
                st.markdown('<div class="regen-btn">', unsafe_allow_html=True)
                if st.button(f"🔄 {name} 再生成", key=f"regen_{idx}"):
                    with st.spinner("再生成中..."):
                        new_data = run_generation(name, angles_info[name], input_image)
                        if new_data:
                            st.session_state.gen_dict[name] = new_data
                            st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    if st.button("4枚まとめて保存", type="primary"):
        json_data = get_b64_json_list(st.session_state.gen_dict, pose_id)
        js_code = f"""
        <script>
            (async function() {{
                const files = {json_data};
                for (let file of files) {{
                    const link = document.createElement('a');
                    link.href = file.data;
                    link.download = file.name;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    await new Promise(r => setTimeout(r, 1000));
                }}
            }})();
        </script>
        """
        components.html(js_code, height=1)
        st.toast("一括保存を開始しました。")
