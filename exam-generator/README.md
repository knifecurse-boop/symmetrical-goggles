# exam-generator 英文試卷 AI 生成器

選擇**雜誌 → 月號 → 單元**，勾選要考的**單字片語、文法、句型、主題與課文**，
再設定**題型與題數**，由 Claude 依教材內容命題，自動組成一份完整試卷，
同時輸出**學生卷**與**教師卷（含答案、解析、命題依據）**。

輸出格式：Word（.docx，可再編輯）、HTML（可直接列印）、Markdown、JSON（原始資料）。

## 支援題型

| 代碼 | 題型 | 說明 |
| --- | --- | --- |
| `vocabulary` | 詞彙題 | 單句四選一，考單元單字片語 |
| `grammar` | 文法選擇題 | 單句四選一，考文法重點與句型 |
| `cloze` | 綜合測驗（克漏字） | AI 依主題撰寫原創短文並挖空 |
| `word_bank` | 文意選填 | 短文 + 10 個字詞庫選項 |
| `reading` | 閱讀測驗 | 延伸主題的原創文章 + 理解題 |
| `translation` | 中譯英 | 須用到指定單字或句型 |
| `sentence_combination` | 句子合併 | 依提示練習指定文法句型 |

新增題型：在 `src/exam_generator/question_types.py` 加一筆 `QuestionType`，
網頁、產生器、排版都會自動支援。

## 安裝

需要 Python 3.10+ 和 Claude API 金鑰：

```bash
cd exam-generator
pip install -e .
export ANTHROPIC_API_KEY=sk-ant-...
```

## 使用方式

### 網頁介面（推薦）

```bash
exam-gen web
```

用瀏覽器打開 http://127.0.0.1:5000，依序：

1. **命題範圍**：選雜誌、月號，勾選單元（可以按「加入其他雜誌或月號」跨期出題）
2. **命題重點**：勾選單字片語／文法／句型／主題與課文，填試卷標題、學生程度、難度
3. **題型與題數**：自己新增大題，或套用「段考標準卷」「單元小考」預設
4. **產生試卷**：每個大題大約需要 1 分鐘，完成後可以在網頁上預覽，也可以下載 Word 或列印用的 HTML

### 命令列

```bash
exam-gen catalog                                   # 列出教材庫中的雜誌、月號、單元與題型
exam-gen generate --spec specs/sample_exam.yaml    # 依設定檔產生試卷到 ./output
exam-gen generate --spec specs/sample_exam.yaml --dry-run   # 只印出要送給 AI 的內容，不花費 API
```

出題設定檔範例見 [`specs/sample_exam.yaml`](specs/sample_exam.yaml)，每個大題可以個別設定
`focus`（只考文法句型等）與 `instructions`（額外命題要求）。

常用參數：`--effort low|medium|high|xhigh|max`（思考深度，預設 `high`；越高品質越好，但越慢越貴）、
`--model`（預設 `claude-opus-5-5`）、`--out`（輸出資料夾）。

## 建立教材庫

教材放在 `library/` 下，**一本雜誌一個資料夾，一期一個 YAML 檔**：

```
library/
  sample-english-monthly/      ← 雜誌代碼
    magazine.yaml              ← 雜誌名稱與程度
    2026-09.yaml               ← 一期（檔名就是月號）
    2026-10.yaml
```

每期的格式（完整範例見 [`library/sample-english-monthly/2026-09.yaml`](library/sample-english-monthly/2026-09.yaml)）：

```yaml
issue: 2026-09
title: 九月號：生活與永續
units:
  - id: U1
    title: Saying Goodbye to Single-Use Plastic
    topic: 環保永續、減塑校園
    article: |
      （課文全文）
    vocabulary:
      - {word: sustainable, pos: adj., meaning: 永續的, example: We need a sustainable way to deal with waste.}
    phrases:
      - {word: run out of, meaning: 用完, example: We ran out of milk.}
    grammar:
      - point: 分詞構句
        explanation: 以過去分詞開頭表示被動或原因
        examples: [Inspired by the moment, the student council launched a campaign.]
    patterns:
      - pattern: It was not until ... that ...
        meaning: 直到……才……
        examples: [It was not until midnight that he finished his homework.]
```

除了 `id` 和 `title`，其他欄位都可以省略；沒有填的部分 AI 就不會拿來命題。
內附的「範例英語月刊」是示範用的虛構教材，換成你們實際使用的雜誌內容即可。

## 運作原理

1. 依選擇的範圍讀取單元教材，只保留勾選的命題重點，整理成命題範圍文字
2. 每個大題呼叫一次 Claude，用 structured outputs 取得固定格式的試題 JSON
   （題幹、選項、答案、中文解析、命題依據）
3. 程式檢查格式：題數、選項數、答案代號、克漏字空格編號、字詞庫是否重複使用等，
   不合格就附上錯誤原因請 AI 重新產生（最多 3 次）
4. 已考過的重點會傳給下一個大題，讓整份試卷盡量涵蓋不同的教材內容
5. 題號跨大題連續編號，文章中的空格也會改成對應題號，最後輸出學生卷與教師卷

> AI 命的題目仍可能有瑕疵（例如答案有爭議、干擾選項也說得通），正式使用前請老師用教師卷檢查一遍。

## 開發

```bash
pip install -e ".[dev]"
pytest
```

測試使用假的 Claude client，不需要 API 金鑰也不會產生費用。
