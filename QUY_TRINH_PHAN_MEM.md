# Quy trình thực hiện phần mềm kiểm tra sáng kiến

## 1. Tính năng

Phần mềm được xây dựng để kiểm tra tương đồng tài liệu sáng kiến trong môi trường local, đồng thời có tùy chọn đánh giá online bằng mô hình OpenAI.

Các tính năng chính:

- Kiểm tra tương đồng tài liệu nội bộ trong corpus local.
- Hỗ trợ định dạng `TXT`, `MD`, `DOCX`, `PDF`.
- Trích xuất nội dung PDF theo nhiều lớp: `pymupdf4llm`, `markitdown`, `PyMuPDF`, và OCR bằng `pytesseract` khi PDF gần như không có text.
- Tự nhận diện phần `Bản mô tả sáng kiến` và bỏ qua phần bìa/hành chính phía trước.
- Tách tài liệu theo khung sáng kiến:
  - `1. Tên sáng kiến`
  - `2. Lĩnh vực áp dụng sáng kiến`
  - `II. Mô tả giải pháp đã biết`
  - `III.1. Nội dung giải pháp`
  - `III.2. Tính mới, tính sáng tạo`
  - `III.3. Phạm vi ảnh hưởng, khả năng áp dụng`
  - `III.4. Hiệu quả, lợi ích thu được`
- Chunk theo đầu mục và đoạn văn, không chỉ chunk đều theo số từ.
- Tạo chỉ mục TF-IDF word n-gram và char n-gram cho tìm kiếm local.
- Tạo semantic embedding local nếu có model trong `models/vietnamese-sbert` hoặc cấu hình `EMBEDDING_MODEL_PATH`.
- So sánh tài liệu kiểm tra với corpus bằng nhiều tín hiệu:
  - TF-IDF word
  - TF-IDF char n-gram
  - shingle overlap
  - semantic embedding cosine nếu có
- Hiển thị đoạn nghi ngờ tương đồng, tên file nguồn, điểm nghi ngờ và mục tương ứng.
- Đánh giá online bằng OpenAI API theo rubric:
  - Tính mới, tính sáng tạo: 30 điểm
  - Hiệu quả áp dụng, lợi ích thu được: 40 điểm
  - Khả năng nhân rộng: 30 điểm
- Chủ động tạo truy vấn online từ `Tên sáng kiến` và yêu cầu quét khoảng 20-30 kết quả đầu tiên.

## 2. Thiết kế hệ thống

Hệ thống được chia thành các module chính:

| Thành phần | File | Vai trò |
|---|---|---|
| Web/API | `app/api.py` | Giao diện web, endpoint kiểm tra file/text, endpoint đánh giá online |
| CLI | `cli.py` | Lệnh build index, kiểm tra file/text, chạy server |
| Cấu hình | `app/config.py` | Cấu hình store, upload, chunk, model embedding, OpenAI model |
| Trích xuất tài liệu | `app/document_extraction.py` | Đọc PDF/DOCX/TXT theo nhiều lớp |
| Extractor tương thích cũ | `app/extractors.py` | Trả text đã cắt từ phần `Bản mô tả sáng kiến` |
| Section/chunk | `app/sectioning.py` | Nhận diện mẫu sáng kiến, tách mục, tạo chunk theo đoạn |
| Build index | `app/indexer.py` | Đọc corpus, chunk, lưu SQLite, tạo TF-IDF và semantic embeddings |
| Lưu trữ | `app/storage.py` | SQLite schema, lưu vectorizer, matrix, metadata |
| Kiểm tra local | `app/detector.py` | Tìm tương đồng local bằng TF-IDF, shingle, semantic |
| Semantic backend | `app/semantic.py` | Load `sentence-transformers` local model và encode text |
| Đánh giá online | `app/online_evaluator.py` | Gọi OpenAI, web search, chấm rubric, so embedding online |
| Giao diện | `app/templates/index.html` | Form kiểm tra local và đánh giá online |

Thiết kế dữ liệu index:

- `data/index.db`: lưu documents và chunks.
- `data/chunk_rows.json`: lưu metadata chunk.
- `data/word_vectorizer.joblib`: vectorizer word TF-IDF.
- `data/char_vectorizer.joblib`: vectorizer char TF-IDF.
- `data/word_matrix.npz`: ma trận word TF-IDF.
- `data/char_matrix.npz`: ma trận char TF-IDF.
- `data/semantic_embeddings.npy`: embedding semantic local, chỉ có khi đã build với model embedding.
- `data/meta.json`: thông tin lần build index.

Metadata chunk hiện gồm:

```json
{
  "chunk_id": 1,
  "doc_id": 1,
  "doc_filename": "example.pdf",
  "chunk_index": 0,
  "section_key": "proposed_solution",
  "section_title": "III.1. Nội dung giải pháp đề nghị công nhận sáng kiến",
  "paragraph_index": 0,
  "heading_path": ["III.1. Nội dung giải pháp đề nghị công nhận sáng kiến"],
  "extractor": "pymupdf4llm",
  "ocr_used": false
}
```

## 3. Các quy trình xử lý

### 3.1. Quy trình cài đặt môi trường

Công nghệ sử dụng:

- Python `.venv`: cô lập thư viện cho phần mềm.
- `pip`: cài dependency.
- `requirements.txt`: danh sách thư viện.
- Tesseract OCR: phần mềm OCR ngoài Python.

Quy trình:

```powershell
D:
cd D:\local_plagiarism_checker
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Kiểm tra OCR:

```powershell
tesseract --list-langs
```

Cần có:

```text
vie
eng
```

Kiểm tra model embedding:

```powershell
python -c "from sentence_transformers import SentenceTransformer; m=SentenceTransformer('D:/local_plagiarism_checker/models/vietnamese-sbert'); print('OK')"
```

### 3.2. Quy trình trích xuất dữ liệu đầu vào

Công nghệ sử dụng:

- `pymupdf4llm`: ưu tiên đọc PDF có text và giữ cấu trúc Markdown.
- `markitdown`: fallback đọc nhiều định dạng về text/Markdown.
- `PyMuPDF`: fallback đọc PDF text cơ bản.
- `pytesseract` + Tesseract OCR: chỉ dùng khi PDF gần như không có text.
- `python-docx`: fallback cho DOCX.

Luồng PDF:

```text
PDF
 -> pymupdf4llm
 -> markitdown
 -> PyMuPDF
 -> pytesseract OCR nếu gần như không có text
```

Ngưỡng hiện tại:

- Text extractor được coi là dùng được nếu có ít nhất khoảng `120` ký tự và tỷ lệ chữ/số đủ tốt.
- OCR chỉ chạy khi gần như không có text, ví dụ dưới khoảng `40` ký tự hoặc tỷ lệ ký tự hợp lệ quá thấp.

Luồng DOCX:

```text
DOCX
 -> markitdown
 -> python-docx nếu markitdown không đủ tốt
```

Luồng TXT/MD:

```text
TXT/MD
 -> đọc trực tiếp bằng encoding phù hợp
```

### 3.3. Quy trình nhận diện mẫu sáng kiến

Công nghệ sử dụng:

- Regex.
- Chuẩn hóa không dấu bằng `unicodedata`.
- Parser nội bộ trong `app/sectioning.py`.

Quy trình:

1. Chuẩn hóa text để nhận diện không phụ thuộc dấu tiếng Việt.
2. Tìm điểm bắt đầu:

```text
ban mo ta sang kien
ban mo ta sang kien kinh nghiem
mo ta sang kien
```

3. Bỏ toàn bộ nội dung trước phần này.
4. Tách các trường:

```text
Tên sáng kiến
Lĩnh vực áp dụng sáng kiến
```

5. Tách các section chính:

```text
II. Mô tả giải pháp đã biết
III.1. Nội dung giải pháp đề nghị công nhận sáng kiến
III.2. Tính mới, tính sáng tạo
III.3. Phạm vi ảnh hưởng, khả năng áp dụng
III.4. Hiệu quả, lợi ích thu được
```

Nếu không nhận diện được section, hệ thống vẫn xử lý toàn bộ phần text sau khi extract, nhưng sẽ fallback chunk theo body.

### 3.4. Quy trình chunk dữ liệu

Công nghệ sử dụng:

- `app/sectioning.py`
- Regex heading.
- Tokenizer nội bộ bằng `TOKEN_RE`.

Quy trình:

1. Nhận `StructuredDocument`.
2. Nếu có section, chunk theo từng section.
3. Trong mỗi section, ưu tiên đoạn văn.
4. Nếu đoạn quá ngắn, gộp các đoạn liền kề.
5. Nếu đoạn quá dài, tách thành chunk nhỏ hơn.
6. Mỗi chunk giữ metadata section.

Thông số hiện tại:

```text
min_words = 45
max_words = 260
```

Fallback:

- Nếu không tạo được structured chunk, hệ thống dùng chunk token cũ:

```text
chunk_size = 220
overlap = 70
```

### 3.5. Quy trình build index corpus

Công nghệ sử dụng:

- `app/indexer.py`
- SQLite.
- `scikit-learn` TF-IDF.
- `sentence-transformers` nếu có embedding model.
- `scipy sparse matrix`.
- `joblib`.

Quy trình:

```text
corpus
 -> extract_document()
 -> parse_structured_document()
 -> chunk_structured_document()
 -> lưu documents/chunks vào SQLite
 -> tạo word TF-IDF matrix
 -> tạo char TF-IDF matrix
 -> nếu có embedding model: tạo semantic_embeddings.npy
```

Lệnh:

```powershell
python cli.py index --corpus .\corpus --store .\data
```

Nếu model local tồn tại ở:

```text
D:\local_plagiarism_checker\models\vietnamese-sbert
```

hệ thống sẽ tự dùng làm `EMBEDDING_MODEL_PATH`.

Kết quả mong muốn:

```text
data/index.db
data/chunk_rows.json
data/word_vectorizer.joblib
data/char_vectorizer.joblib
data/word_matrix.npz
data/char_matrix.npz
data/semantic_embeddings.npy
data/meta.json
```

Nếu không có `semantic_embeddings.npy`, hệ thống vẫn chạy local bằng TF-IDF nhưng chưa có semantic embedding.

### 3.6. Quy trình kiểm tra local

Công nghệ sử dụng:

- `app/detector.py`
- TF-IDF word n-gram.
- TF-IDF char n-gram.
- Shingle overlap.
- SentenceTransformer semantic embedding nếu có.
- Cosine similarity.

Quy trình:

```text
File hoặc text cần kiểm tra
 -> extract text
 -> cắt từ Bản mô tả sáng kiến
 -> chunk theo section/paragraph
 -> với từng query chunk:
      -> TF-IDF search
      -> semantic search nếu có embeddings
      -> shingle match
      -> combine score
 -> gom kết quả theo document
 -> trả matches/passages/score
```

Công thức hiện tại:

- Không có semantic:

```text
score = 0.45 * tfidf + 0.55 * shingle
```

- Có semantic:

```text
score = 0.40 * semantic + 0.35 * tfidf + 0.25 * shingle
```

### 3.7. Quy trình đánh giá online bằng OpenAI

Công nghệ sử dụng:

- OpenAI Responses API.
- Web search tool của OpenAI.
- `gpt-5.5` theo cấu hình mặc định.
- Structured JSON schema.
- Semantic embedding local hoặc fallback TF-IDF cosine cho so sánh online.

Biến môi trường:

```powershell
$env:OPENAI_API_KEY="sk-..."
$env:OPENAI_EVAL_MODEL="gpt-5.5"
$env:ONLINE_SEARCH_RESULTS="30"
```

Quy trình:

```text
Tài liệu sáng kiến
 -> extract text
 -> parse structured document
 -> lấy Tên sáng kiến
 -> sinh truy vấn online
 -> yêu cầu GPT + web search quét 20-30 kết quả đầu tiên
 -> tìm nguồn tương tự
 -> chấm rubric 30/40/30
 -> trả JSON kết quả
```

Rubric:

| Tiêu chí | Điểm |
|---|---:|
| Tính mới, tính sáng tạo | 30 |
| Hiệu quả áp dụng, lợi ích thu được | 40 |
| Khả năng nhân rộng | 30 |
| Tổng | 100 |

Output gồm:

- Tên sáng kiến.
- Danh sách truy vấn online.
- Số nguồn tìm thấy/đã xem.
- Nguồn online tương tự.
- Điểm từng tiêu chí.
- Tổng điểm.
- Nhận xét cuối.
- Độ tin cậy.
- So sánh embedding online.

### 3.8. Quy trình chạy web

Công nghệ sử dụng:

- FastAPI.
- Uvicorn.
- Jinja2 template.

Lệnh:

```powershell
python cli.py serve --store .\data --host 127.0.0.1 --port 8000
```

Mở trình duyệt:

```text
http://127.0.0.1:8000
```

Giao diện hỗ trợ:

- Kiểm tra local bằng text hoặc file.
- Đánh giá online bằng GPT.
- Hiển thị điểm nghi ngờ, passages, nguồn corpus.
- Hiển thị điểm rubric và nguồn online tương tự.

## 4. Hướng cải tiến

### 4.1. Cải tiến trích xuất OCR

- Thêm log chi tiết cho từng file:
  - extractor nào được dùng
  - số ký tự trích xuất
  - OCR có chạy không
  - lý do fallback
- Cho phép cấu hình chế độ OCR:

```text
ocr = never | auto | always
```

- Tối ưu OCR theo trang: chỉ OCR trang không có text, không OCR toàn bộ PDF.
- Lưu cache OCR để không xử lý lại file cũ.

### 4.2. Cải tiến chunk

- Thêm thống kê vào `meta.json`:

```json
{
  "chunking_strategy": "structured_sections_with_paragraphs",
  "structured_chunks_indexed": 0,
  "fallback_chunks_indexed": 0
}
```

- Tách tốt hơn các mục con như:

```text
Biện pháp 1
Biện pháp 2
a)
b)
1.1
1.2
```

- Cho phép cấu hình `min_words`, `max_words` từ CLI.

### 4.3. Cải tiến semantic embedding

- Tách rõ model embedding cho local và online.
- Thêm kiểm tra tự động sau build index:

```text
semantic_embeddings.npy tồn tại
số vector = số chunk
dimension đúng
```

- Hỗ trợ nhiều model:
  - Vietnamese SBERT
  - multilingual E5
  - BGE multilingual
- Lưu thêm embedding theo section-level để so tổng quan mục `III.2`, `III.3`, `III.4`.

### 4.4. Cải tiến đánh giá online

- Tách bước web search thành cache riêng để giảm chi phí API.
- Lưu lại kết quả online theo hash tài liệu.
- Cho phép người dùng xem 20-30 nguồn đã quét.
- Thêm mức rủi ro copy:

```text
low | medium | high
```

- Thêm chế độ chỉ search online nhưng không chấm rubric.

### 4.5. Cải tiến giao diện

- Hiển thị rõ extractor đã dùng cho file upload.
- Hiển thị section tương ứng của từng đoạn trùng.
- Thêm bộ lọc kết quả theo:
  - mức rủi ro
  - tên trường
  - cấp học
  - lĩnh vực áp dụng
- Cho phép xuất báo cáo `PDF/DOCX`.

### 4.6. Cải tiến vận hành

- Thêm file `.env` để cấu hình riêng cho phần mềm:

```env
OPENAI_API_KEY=
OPENAI_EVAL_MODEL=
ONLINE_SEARCH_RESULTS=
EMBEDDING_MODEL_PATH=
```

- Thêm job queue cho index corpus lớn.
- Thêm incremental indexing: chỉ index lại file mới hoặc file thay đổi.
- Thêm audit log cho các lần kiểm tra.
- Thêm phân quyền người dùng nếu triển khai nội bộ nhiều người.

## 5. Ghi chú vận hành quan trọng

- `.venv` chỉ chứa Python và thư viện, không chứa tài liệu index.
- File gốc nằm trong `corpus`.
- Index nằm trong `data`.
- Muốn áp dụng thay đổi chunk/extract/embed mới, phải build lại index.
- Muốn dùng semantic embedding local, cần có model local và build index tạo được `data/semantic_embeddings.npy`.
- Muốn dùng đánh giá online, cần `OPENAI_API_KEY` còn quota.
