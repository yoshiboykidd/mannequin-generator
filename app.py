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
        # マネキンは色数が少ないのでPNGの方が綺麗で軽量化しやすい場合もあるが
        # ここでは確実な容量削減のためにJPEGを使用
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        size_kb = len(buf.getvalue()) / 1024
        if size_kb <= max_kb or quality <= 10:
            break
        quality -= 5
    return buf.getvalue(), size_kb

def get_safe_angle_name(name):
    """アングル名を英語のファイル名用に変換"""
    mapping = {
        "真正面 (Front)": "Front",
        "斜め前 (Quarter)": "Quarter",
        "下から (Low Angle)": "Low",
        "斜め上から (High Angle)": "High"
    }
    return mapping.get(name, "pose")

def get_b64_json_list(image_list, pose_id):
    """JavaScript用：ポーズ番号を含めたファイル名リストを作成"""
    js_data = []
    for name, data in image_list:
        angle_fn = get_safe_angle_name(name)
        # 形式: pose_[番号]_[アングル].jpg
        filename = f"pose_{pose_id}_{angle_fn}.jpg"
        b64 = base64.b64encode(data).decode()
        js_data.append(f'{{ "data": "data:image/jpeg;base64,{b64}", "name": "{filename}" }}')
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

st.title("🤖 マネキンポーズ素材一括生成")
st.write("設定: 薄いグレーのマネキン / 完全な白背景 / 台座除去 / 4アングル")

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
    st.header("1. 保存設定")
    pose_id = st.text_input("ポーズ番号 (例: 01, 02...)", value="01")
    st.info(f"保存名: pose_{pose_id}_[Angle].jpg")
    
    st.divider()
    st.header("2. 写真をアップロード")
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
        "斜め上から (High Angle)": "A high-angle shot from diagonally above (bird's-
