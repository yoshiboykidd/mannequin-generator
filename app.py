# --- 生成ボタン内の処理 ---
if st.button("マネキン素材を生成", type="primary"):
    with st.spinner('生成中...'):
        
        # プロンプトでアスペクト比を強く指定
        prompt = """
        A high-quality studio photograph of a neutral grey plastic mannequin.
        Replicate the exact pose and body orientation of the person in the image.
        No hair, no clothes, no facial features. 
        Smooth, matte surface, plain white background. 
        Crucially, the image must be in a 2:3 vertical aspect ratio.
        """

        try:
            # 修正ポイント：GenerationConfigを標準的なものにする（または渡さない）
            # image_configを削除しました
            generation_config = {
                "temperature": 0.4,
                "top_p": 0.9,
            }

            response = model.generate_content(
                [prompt, input_image],
                generation_config=generation_config
            )

            # 画像データの取得
            image_data = None
            for part in response.parts:
                if hasattr(part, 'inline_data'):
                    image_data = part.inline_data.data
                    break
            
            if image_data:
                generated_img = Image.open(io.BytesIO(image_data))
                
                # --- ここでサイズ(1000px)、比率(2:3)、容量(300kb)を強制的に調整 ---
                # 前回の回答で作成した process_and_compress_image 関数をここで呼び出します
                final_bytes, final_size, final_quality = process_and_compress_image(generated_img)
                
                st.success(f"生成完了！ (サイズ: {final_size:.1f}kb / 品質: {final_quality})")
                st.image(final_bytes, caption="生成されたマネキン素材", use_container_width=True)
                
                st.download_button(
                    label="ポーズ素材をダウンロード",
                    data=final_bytes,
                    file_name="mannequin_pose.jpg",
                    mime="image/jpeg"
                )
