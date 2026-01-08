import streamlit as st
import google.generativeai as genai
from PIL import Image
import io

# ==========================================
# 設定・準備
# ==========================================

# ページ設定
st.set_page_config(
    page_title="Pose Mannequin Generator",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 ポーズ素材生成ツール (マネキン素体)")
st.write("写真をアップロードすると、同じポーズの「服を着ていないマネキン素体」を生成します。")

# --- APIキーの設定 ---
# 【重要】Streamlit Cloudで動かす場合は、この部分を直接書かず、
# Streamlitの「Secrets」機能を使って設定してください。
# ローカルで試す場合は、ここに直接文字列で入れても動きますが、GitHubには上げないでください。
try:
    # Streamlit Secretsからキーを取得する推奨方法
    api_key = st.secrets["GOOGLE_API_KEY"]
except FileNotFoundError:
    # ローカルテスト用（secrets.tomlがない場合）のフォールバック
    # 本番環境では使用しないでください。
    api_key = "YOUR_API_KEY_HERE" # ここに直接キーを入れるのはテスト時のみ！
    st.warning("⚠️ APIキーがコードに直接記述されています。本番環境ではSecretsを使用してください。")

if not api_key or api_key == "YOUR_API_KEY_HERE":
    st.error("APIキーが設定されていません。")
    st.stop()

# Gemini APIの構成
genai.configure(api_key=api_key)

# --- モデルの選択 ---
# 画像を入力して画像を生成できるモデルを指定する必要があります。
# ご利用の環境で利用可能な最新のモデル名に変更してください。
# 例: 'gemini-1.5-pro-latest', 'gemini-pro-vision' など
# ※注意: すべてのGeminiモデルが画像「生成」に対応しているわけではありません。
# 着せ替えツールで成功しているモデル名があれば、それを使用してください。
MODEL_NAME = 'gemini-1.5-pro-latest' 

try:
    model = genai.GenerativeModel(MODEL_NAME)
except Exception as e:
    st.error(f"モデルの初期化に失敗しました。モデル名を確認してください: {e}")
    st.stop()


# ==========================================
# メイン処理
# ==========================================

# サイドバー設定
with st.sidebar:
    st.header("設定")
    bg_color = st.selectbox(
        "背景色",
        ["Plain White (白無地)", "Plain Grey (グレー無地)"],
        index=0
    )
    bg_prompt_part = "plain white studio background" if bg_color == "Plain White (白無地)" else "plain neutral grey studio background"

# 画像アップロード
uploaded_file = st.file_uploader("ポーズの元となる写真をアップロード (JPG, PNG)", type=["jpg", "png", "jpeg"])

if uploaded_file is not None:
    # 画像を開いて表示
    input_image = Image.open(uploaded_file)
    st.image(input_image, caption="元画像", use_column_width=True)

    # 生成ボタン
    if st.button("マネキン素体に変換を開始", type="primary"):
        with st.spinner('AIがポーズを解析し、素体を生成しています...（数十秒かかる場合があります）'):
            
            # --- プロンプトの定義 (ここが最も重要) ---
            # 服や髪を一切描かないように強く指示します。
            prompt = f"""
            Generate a photograph of a completely featureless, bald, unclothed grey plastic mannequin base body.
            The mannequin must be standing in the exact same physiological pose and body angle as the person in the provided reference image.
            Crucially, there must be ABSOLUTELY NO hair, NO clothing, NO facial features (eyes, nose, mouth), and NO accessories.
            Just a smooth, neutral grey articulated figure against a {bg_prompt_part}.
            Focus strictly on replicating the limb geometry and posture from the input image.
            """

            try:
                # API呼び出し
                # 画像とテキストプロンプトを同時に渡します
                response = model.generate_content([prompt, input_image])

                # --- レスポンスの処理 ---
                # ※ご使用のSDKバージョンやモデルによってレスポンス構造が異なる場合があります。
                # 着せ替えツールで画像が取得できている方法に合わせて調整が必要です。
                
                generated_image = None
                
                # パターンA: response.partsの中に画像データ(blob)が含まれる場合（最近のSDKの一般的な挙動）
                if hasattr(response, 'parts'):
                    for part in response.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            image_data = part.inline_data.data
                            generated_image = Image.open(io.BytesIO(image_data))
                            break
                
                # パターンB: もしAPIが画像URLをテキストで返してくるタイプの場合（古いAPIなど）
                # if not generated_image and response.text.startswith("http"):
                #      import requests
                #      img_response = requests.get(response.text)
                #      generated_image = Image.open(io.BytesIO(img_response.content))

                # 画像が生成できたか確認して表示
                if generated_image:
                    st.success("生成完了！")
                    st.image(generated_image, caption="生成されたマネキン素体", use_column_width=True)
                    
                    # ダウンロードボタンの作成
                    buf = io.BytesIO()
                    generated_image.save(buf, format="PNG")
                    byte_im = buf.getvalue()
                    st.download_button(
                        label="生成画像をダウンロード (PNG)",
                        data=byte_im,
                        file_name="mannequin_pose.png",
                        mime="image/png"
                    )
                else:
                    # 画像データが見つからなかった場合
                    st.warning("画像が生成されませんでした。テキストレスポンスが表示されるか確認してください。")
                    if response.text:
                        st.write("APIからの応答（テキスト）:", response.text)

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                st.info("ヒント: 使用しているモデルが画像生成に対応していないか、APIキーの設定が間違っている可能性があります。")
