from app.detector import HybridDetector
from app.config import DEFAULT_STORE_DIR
import json

d = HybridDetector(DEFAULT_STORE_DIR)

r = d.check_text("Lớp chúng tôi mỗi trẻ với mỗi tính cách khác nhau. Có những trẻ đến lớp rất vui vẻ, tích cực tham gia hoạt động, ngược lại có nhiều cháu lại nhút nhát, hay khóc nhè và thường rất ít khi bộc lộ cảm xúc của mình.")

print("Tổng results:", len(r["results"]))
for x in r["results"][:5]:
    print(f"chunk_id={x['chunk_id']} score={x['score']:.3f} tfidf={x['tfidf']:.3f} sem={x['semantic']:.3f}")

with open(DEFAULT_STORE_DIR / "chunk_rows.json", encoding="utf-8") as f:
    rows = json.load(f)

print("\nTổng chunk_rows:", len(rows))
print("chunk_rows[0]:", rows[0])
print("chunk_rows[-1]:", rows[-1])