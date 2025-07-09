# kf2-status-viewer
Steam APIで取得できるKF2の統計情報を表示します  
※統計情報は合っているかわかりません。  
※ClaudeとGeminiが作りました  
※使用は自己責任でお願いします  

## 必要なもの
* Steam API キー
* StreamID64
    * https://steamid.io/ で自分のsteam user pageのURLを入力すると取得できます
* Steamプロフィールの公開
    * Steamプロフィールの「ゲームの詳細」を非公開に設定している場合、APIでデータを取得できません


## 手順

1. 起動する
    ```
    $ streamlit run simple.py (または colorful.py)
    ```

2. **Stream APIキー**を入力する

3. 自分の**StreamID64**を入力する

### colorful
![スクリーンショット 2025-07-09 213417](https://github.com/user-attachments/assets/5dc66fb4-58aa-4d5b-be7b-b05bf32b3812)


### simple
![スクリーンショット 2025-07-09 213354](https://github.com/user-attachments/assets/cc70ded2-18c1-4a69-80df-4c6cdee9e54c)
