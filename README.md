# Local Plagiarism Checker

Bộ code này tạo một hệ thống kiểm tra đạo văn chạy **local/offline** với corpus nội bộ có sẵn.

Nó được tối ưu theo hướng thực dụng cho tiếng Việt:
- dùng **word TF-IDF (1-3 gram)** để bắt copy theo cụm từ;
- dùng **char n-gram TF-IDF (3-5)** để chịu lỗi chính tả nhẹ, xuống dòng, khác dấu câu, và giảm phụ thuộc tokenizer;
- có thể bật thêm **semantic backend** từ một **sentence-transformer local** nếu bạn đã có model trong máy.

## Tính năng

- Index tài liệu trong thư mục local.
- Hỗ trợ `TXT`, `MD`, `DOCX`, `PDF`.
- Chạy kiểm tra qua **CLI** hoặc **web UI**.
- Không gọi Internet.
- Có báo cáo:
  - điểm nghi ngờ tổng hợp;
  - top tài liệu giống nhất;
  - các đoạn văn trùng / rất giống.

## Cấu trúc thư mục

```text
local_plagiarism_checker/
├── app/
│   ├── api.py
│   ├── config.py
│   ├── detector.py
│   ├── extractors.py
│   ├── indexer.py
│   ├── semantic.py
│   ├── storage.py
│   ├── utils_text.py
│   └── templates/
│       └── index.html
├── cli.py
├── requirements.txt
├── requirements-semantic.txt
├── Dockerfile
├── docker-compose.yml
├── examples/
│   └── corpus/
└── tests/
```

## Cài đặt nhanh

### Cách 1: chạy trực tiếp với Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Nếu bạn muốn bật semantic backend bằng model local:

```bash
pip install -r requirements-semantic.txt
```

## Chuẩn bị corpus

Đặt dữ liệu vào một thư mục, ví dụ:

```text
./corpus/
  bai_01.docx
  bai_02.pdf
  bao_cao_2024.txt
  luan_van_a.md
```

## Build index

```bash
python cli.py index --corpus ./corpus --store ./data
```

Ví dụ có semantic model local đã tải sẵn:

```bash
python cli.py index \
  --corpus ./corpus \
  --store ./data \
  --semantic-model-path ./models/your_local_sentence_transformer
```

Kết quả sẽ tạo ra:
- `index.db`: SQLite lưu văn bản và chunk
- `word_vectorizer.joblib`, `char_vectorizer.joblib`
- `word_matrix.npz`, `char_matrix.npz`
- `meta.json`, `chunk_rows.json`
- `semantic_embeddings.npy` nếu bật semantic

## Kiểm tra một tệp

```bash
python cli.py check-file --file ./input/bai_can_kiem_tra.docx --store ./data
```

Xuất JSON:

```bash
python cli.py check-file --file ./input/bai_can_kiem_tra.docx --store ./data --json
```

## Kiểm tra văn bản trực tiếp

```bash
python cli.py check-text --text "Nội dung cần kiểm tra" --store ./data
```

Hoặc đọc từ file text:

```bash
python cli.py check-text --text-file ./input/query.txt --store ./data
```

Hoặc đọc từ stdin:

```bash
echo "Nội dung cần kiểm tra" | python cli.py check-text --stdin --store ./data
```

## Chạy web UI local

```bash
python cli.py serve --store ./data --host 127.0.0.1 --port 8000
```

Mở trình duyệt tại:

```text
http://127.0.0.1:8000
```

## Chạy bằng Docker

Build:

```bash
docker build -t local-plagiarism-checker .
```

Run:

```bash
docker run --rm -p 8000:8000 \
  -e PLAGIARISM_STORE=/app/data \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/corpus:/app/corpus \
  local-plagiarism-checker
```

Hoặc dùng compose:

```bash
docker compose up --build
```

## Cách chấm điểm

Điểm cuối cùng là tổ hợp của các tín hiệu sau:
- mức tương đồng của các chunk giống nhất;
- độ phủ số chunk query bị trùng;
- độ giao nhau của word shingles;
- độ phủ ở mức passage/sentence.

Điểm này là **điểm nghi ngờ tương đồng**, không phải kết luận vi phạm học thuật.

## Vì sao code này hợp với tiếng Việt

- tiếng Việt có khoảng trắng giữa âm tiết, không phải luôn giữa “từ ghép” theo nghĩa ngôn ngữ học;
- vì vậy **char n-gram** giúp hệ thống bền hơn nếu không có tokenizer chuyên biệt;
- khi cần nâng cấp, bạn có thể dùng thêm semantic model local để bắt paraphrase tốt hơn.

## Gợi ý triển khai thực tế

Nếu corpus dưới khoảng vài chục nghìn tài liệu, bản này chạy ổn trên một máy nội bộ.

Nếu corpus lớn hơn, bạn nên nâng cấp theo hướng:
- tách bước candidate retrieval và passage alignment;
- đưa sparse matrix sang dịch vụ riêng hoặc ANN index;
- thêm job queue để reindex nền;
- thêm phân quyền và audit log;
- thêm API import tự động từ thư mục mạng hoặc DMS.

## Hạn chế hiện tại

- chưa có OCR cho PDF scan hình ảnh;
- chưa có cơ chế incremental indexing thông minh;
- chưa có phân quyền người dùng;
- chưa có highlight trực tiếp trong file gốc PDF/DOCX;
- semantic backend chỉ hoạt động khi bạn đã có model local và thư viện tương ứng.

## Chạy smoke test

```bash
python -m pytest tests/test_smoke.py
```

## Mẹo cấu hình

- corpus nhiều tài liệu ngắn: giảm `--chunk-size` xuống `120-160`.
- tài liệu dài: giữ `--chunk-size` khoảng `180-260` và overlap `50-80`.
- muốn nghiêm hơn: tăng ngưỡng trong `MIN_CHUNK_SCORE` ở `app/config.py`.
- muốn bắt paraphrase tốt hơn: bật semantic backend local.

