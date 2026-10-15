# audio-clipper

根據逐字稿「腳本」，自動比對音檔中對應的位置，並批次剪輯匯出多個音檔片段。

不需要腳本裡有時間碼——只要你貼上想剪的那段文字，工具會用語音辨識
（[faster-whisper](https://github.com/SYSTRAN/faster-whisper)）把整個音檔轉成逐字稿，
再用模糊字串比對（[rapidfuzz](https://github.com/rapidfuzz/RapidFuzz)）找出每段文字
在音檔裡的起訖時間，最後用 `ffmpeg` 剪下並匯出。

## 安裝

需要 Python 3.9+ 以及系統已安裝 `ffmpeg` / `ffprobe`：

```bash
# macOS
brew install ffmpeg

# Debian / Ubuntu
sudo apt install ffmpeg
```

安裝本工具：

```bash
pip install -e .
```

## 腳本格式

建立一個純文字檔，用 `=== 輸出檔名 ===` 標記每一段要剪的片段，
**輸出檔名的副檔名就是匯出的音檔格式**（例如 `.mp3`、`.wav`），
標頭下面接的文字就是該段的逐字稿內容（可以跨多行）：

```text
=== 01_開場白.mp3 ===
大家好，歡迎收看這次的節目，今天要跟大家分享三個非常實用的技巧。

=== 02_重點一.mp3 | padding=0.3 ===
第一個技巧就是每天花十分鐘整理今天學到的東西，長期下來效果非常驚人。

=== 03_結尾.wav ===
好的，以上就是今天的分享，我們下次再見，掰掰。
```

標頭裡可以用 `| padding=秒數` 覆寫這一段前後留白的秒數（預設用 `--padding` 的值）。

完整範例見 [`examples/sample_script.txt`](examples/sample_script.txt)。

## 使用方式

```bash
audio-clipper --audio 節目錄音.mp3 --script script.txt --output-dir out/
```

常用參數：

- `--language zh`：音檔是中文時建議指定，加快辨識並提升準確度（不指定則自動偵測）
- `--model small`：faster-whisper 模型大小（`tiny`/`base`/`small`/`medium`/`large-v3`），模型越大越準但越慢
- `--dry-run`：只顯示比對到的時間區間與信心分數，不實際剪輯匯出，方便先確認比對是否正確
- `--padding 0.15`：每段片段前後留白秒數，避免掐頭去尾
- `--min-score 70`：比對信心分數低於此值時會標記警告，提醒人工複查該片段

第一次執行會需要跑完整段語音辨識（依音檔長度與模型大小需要一些時間），
辨識結果會快取在音檔旁邊（`<檔名>.<hash>.transcript.json`），
之後只要腳本內容變動、重新匯出，就不用再重跑一次語音辨識。用 `--no-cache` 可強制重新辨識。

## 運作原理

1. 解析腳本，取得每段的輸出檔名與逐字稿文字
2. 用 faster-whisper 對整個音檔做語音辨識，取得逐詞時間戳記
3. 把每段逐字稿文字（去除空白標點後）用模糊比對定位到辨識結果中最接近的一段連續文字，
   取得該段對應的起訖時間，並容許少量辨識錯字
4. 對每段時間加上前後留白（padding），並用 `ffmpeg` 剪下匯出成腳本裡指定的檔名與格式

比對是「模糊」的，因此語音辨識偶爾的錯字不會讓整段比對失敗，但如果稿子跟實際錄音
差異太大（例如大幅改寫過的逐字稿），比對信心分數會偏低，工具會在報告中標記
`⚠ 建議人工複查`，此時建議對照 `--dry-run` 的輸出手動確認時間點是否正確。

## 開發

```bash
pip install -e ".[dev]"
pytest
```

解析與比對邏輯（`script_parser.py`、`matcher.py`）不需要 `ffmpeg` 或實際跑語音辨識即可測試。

## 其他工具

- [`exam-generator/`](exam-generator/)：英文試卷 AI 生成器，依雜誌月號單元的單字、文法、句型與主題自動命題並組成試卷。
