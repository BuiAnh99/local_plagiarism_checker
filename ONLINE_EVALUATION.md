# Online Evaluation Setup

Tinh nang danh gia online la tuy chon va khong anh huong den che do kiem tra local.

## Bien moi truong

```powershell
$env:OPENAI_API_KEY="your_api_key"
$env:OPENAI_EVAL_MODEL="gpt-5.5"
$env:ONLINE_SEARCH_RESULTS="30"
$env:EMBEDDING_MODEL_PATH="D:\models\your_local_sentence_transformer"
```

`ONLINE_SEARCH_RESULTS` nen nam trong khoang 20-30. He thong se tu gioi han ve khoang nay.

## OCR

`pytesseract` can chuong trinh Tesseract OCR cai tren may, khong chi la thu vien Python.
Neu PDF da co text, he thong se uu tien `pymupdf4llm` va `markitdown`, khong OCR mac dinh.

## Luong xu ly

1. Trich xuat tai lieu bang `pymupdf4llm`, fallback sang `markitdown`, sau do `pytesseract` khi can OCR.
2. Cat noi dung tu phan `Ban mo ta sang kien`.
3. Tach cac muc `II`, `III.1`, `III.2`, `III.3`, `III.4`.
4. Chunk theo dau muc va doan van de index local.
5. Neu co `EMBEDDING_MODEL_PATH` hoac `SEMANTIC_MODEL_PATH`, he thong tao semantic embeddings cho chunk local khi build index.
6. Khi kiem tra tai lieu, query cung duoc cat theo cau truc dau muc/doan truoc khi so voi corpus.
7. Khi danh gia online, he thong lay `Ten sang kien`, tao truy van, yeu cau quet 20-30 ket qua dau tien, roi cham rubric 30/40/30.
8. Ket qua online uu tien so sanh semantic embedding tren cac nguon/excerpt online tim duoc; neu khong co model embedding thi fallback ve TF-IDF cosine.
