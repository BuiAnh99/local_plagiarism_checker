$ErrorActionPreference = "Stop"

$OutputPath = Join-Path (Resolve-Path ".").Path "ban_sang_kien_kinh_nghiem_phan_mem_kiem_tra_sang_kien.docx"
$TempDir = Join-Path $env:TEMP ("initiative_docx_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $TempDir | Out-Null

function X([string]$Text) {
    return [System.Security.SecurityElement]::Escape($Text)
}

function Para([string]$Text, [string]$Style = "Normal", [string]$Align = "", [bool]$Bold = $false, [bool]$Italic = $false) {
    $pPr = ""
    if ($Style -ne "Normal") { $pPr += "<w:pStyle w:val=`"$Style`"/>" }
    if ($Align) { $pPr += "<w:jc w:val=`"$Align`"/>" }
    if ($pPr) { $pPr = "<w:pPr>$pPr</w:pPr>" }
    $rPr = ""
    if ($Bold) { $rPr += "<w:b/>" }
    if ($Italic) { $rPr += "<w:i/>" }
    if ($rPr) { $rPr = "<w:rPr>$rPr</w:rPr>" }
    return "<w:p>$pPr<w:r>$rPr<w:t xml:space=`"preserve`">$(X $Text)</w:t></w:r></w:p>"
}

function Bullet([string]$Text) {
    return "<w:p><w:pPr><w:pStyle w:val=`"Bullet`"/></w:pPr><w:r><w:t xml:space=`"preserve`">- $(X $Text)</w:t></w:r></w:p>"
}

function Cell([string]$Text, [bool]$Header = $false) {
    $shade = ""
    $rPr = ""
    if ($Header) {
        $shade = "<w:shd w:fill=`"EAF2F8`"/>"
        $rPr = "<w:rPr><w:b/></w:rPr>"
    }
    return "<w:tc><w:tcPr><w:tcW w:w=`"2500`" w:type=`"dxa`"/>$shade</w:tcPr><w:p><w:r>$rPr<w:t xml:space=`"preserve`">$(X $Text)</w:t></w:r></w:p></w:tc>"
}

function Table($Rows) {
    $xml = "<w:tbl><w:tblPr><w:tblStyle w:val=`"TableGrid`"/><w:tblW w:w=`"0`" w:type=`"auto`"/><w:tblLook w:firstRow=`"1`" w:lastRow=`"0`" w:firstColumn=`"0`" w:lastColumn=`"0`" w:noHBand=`"0`" w:noVBand=`"1`"/></w:tblPr><w:tblGrid><w:gridCol w:w=`"2400`"/><w:gridCol w:w=`"3600`"/><w:gridCol w:w=`"3600`"/></w:tblGrid>"
    for ($i = 0; $i -lt $Rows.Count; $i++) {
        $isHeader = ($i -eq 0)
        $xml += "<w:tr>"
        foreach ($c in $Rows[$i]) { $xml += Cell $c $isHeader }
        $xml += "</w:tr>"
    }
    $xml += "</w:tbl>"
    return $xml
}

$body = New-Object System.Collections.Generic.List[string]

$body.Add((Para "BẢN SÁNG KIẾN KINH NGHIỆM" "Title" "center" $true $false))
$body.Add((Para "Phần mềm kiểm tra, đối chiếu và hỗ trợ đánh giá sáng kiến kinh nghiệm" "Subtitle" "center" $false $false))
$body.Add((Para "Tài liệu này mô tả giải pháp theo cách dễ hiểu cho người không chuyên về lập trình. Trọng tâm là phần mềm đã hoàn thiện: đọc tài liệu sáng kiến, trích đúng phần cần đối chiếu, so sánh với kho tài liệu nội bộ, hỗ trợ quét trực tuyến, chấm điểm theo rubric và xuất báo cáo Word." "Normal" "both"))

$body.Add((Para "1. Mô tả giải pháp đã có" "Heading1"))
$body.Add((Para "Trước khi có phần mềm, việc kiểm tra sáng kiến thường được thực hiện thủ công. Người phụ trách phải mở từng file, đọc nội dung, tự tìm các đoạn nghi ngờ trùng lặp, tra cứu trên Internet và ghi nhận xét bằng tay. Cách làm này phụ thuộc nhiều vào kinh nghiệm cá nhân, mất thời gian khi số lượng hồ sơ lớn và khó đảm bảo cách đánh giá giữa các tài liệu là thống nhất." "Normal" "both"))
$body.Add((Para "Một số công cụ kiểm tra trùng lặp phổ biến có thể hỗ trợ phát hiện sao chép, nhưng thường không phù hợp hoàn toàn với hồ sơ sáng kiến kinh nghiệm vì chúng không hiểu cấu trúc mẫu biểu, không chỉ tập trung vào phần mô tả giải pháp, khó đọc tốt tài liệu scan tiếng Việt và có thể phát sinh chi phí cao nếu dùng thường xuyên." "Normal" "both"))
$body.Add((Para "Giải pháp mới là một phần mềm chạy cục bộ trên máy tính hoặc trong container Docker. Phần mềm xây dựng một kho dữ liệu nội bộ từ các sáng kiến đã có, sau đó dùng kho này để đối chiếu các hồ sơ mới. Hệ thống chỉ bắt đầu kiểm tra từ mục 'III. Nội dung giải pháp đề nghị công nhận sáng kiến', tránh đưa phần thông tin hành chính hoặc phần mô tả giải pháp đã biết vào kết quả so sánh." "Normal" "both"))

$body.Add((Para "Các điểm chính của giải pháp:" "Heading2"))
$body.Add((Bullet "Đọc được nhiều loại tài liệu thường gặp như PDF, DOC, DOCX và file scan cần OCR."))
$body.Add((Bullet "Ưu tiên đọc chữ thật trong tài liệu bằng PyMuPDF4LLM và MarkItDown; chỉ dùng OCR khi PDF gần như không có văn bản."))
$body.Add((Bullet "Tự tách nội dung theo đầu mục của mẫu sáng kiến, ưu tiên đoạn văn tự nhiên thay vì cắt cơ học theo số ký tự."))
$body.Add((Bullet "Dùng mô hình embedding tiếng Việt chạy cục bộ để hiểu độ gần nghĩa giữa các đoạn, không chỉ so khớp từ khóa."))
$body.Add((Bullet "Có thể kiểm tra một hoặc nhiều tài liệu cùng lúc; mỗi tài liệu sau khi đối chiếu được xuất một báo cáo Word riêng."))
$body.Add((Bullet "Có cơ chế index tăng dần: chỉ thêm file mới vào kho, không phải quét lại toàn bộ kho mỗi lần."))
$body.Add((Bullet "Có tùy chọn dùng GPT và tìm kiếm trực tuyến để tham khảo 20-30 kết quả đầu tiên theo tên sáng kiến, phục vụ đánh giá tính mới, hiệu quả và khả năng nhân rộng."))

$body.Add((Para "2. Nội dung của app" "Heading1"))
$body.Add((Para "Phần mềm gồm các nhóm chức năng chính. Người dùng thao tác qua giao diện web nội bộ, không cần biết câu lệnh lập trình. Phần xử lý phía sau do các thư viện Python, mô hình ngôn ngữ và công cụ đọc tài liệu đảm nhiệm." "Normal" "both"))

$featureRows = @(
    @("Nhóm tính năng", "Cách người dùng nhìn thấy", "Công nghệ đứng phía sau"),
    @("Nạp kho dữ liệu", "Đưa các sáng kiến cũ vào thư mục corpus và bấm/chạy index để tạo kho đối chiếu.", "SQLite lưu thông tin tài liệu; scikit-learn tạo chỉ mục TF-IDF; sentence-transformers tạo vector embedding tiếng Việt; joblib và NumPy lưu dữ liệu tối ưu."),
    @("Đọc tài liệu", "Tải lên PDF, DOC, DOCX, kể cả tài liệu scan.", "PyMuPDF4LLM đọc PDF theo cấu trúc; MarkItDown chuyển đổi tài liệu Office/PDF sang văn bản; PyMuPDF đọc lớp chữ; Tesseract OCR đọc ảnh khi không có chữ thật."),
    @("Tách đúng phần cần kiểm tra", "Hệ thống bỏ qua phần đầu hồ sơ và chỉ đối chiếu từ mục III của bản mô tả sáng kiến.", "Bộ nhận diện đầu mục tiếng Việt, chuẩn hóa Unicode và biểu thức nhận dạng mục I, II, III, III.1, III.2, III.3, III.4."),
    @("Chia đoạn thông minh", "Kết quả hiển thị theo đoạn văn/đầu mục dễ đọc.", "Chunk theo cấu trúc mục và đoạn văn, có giới hạn độ dài để đoạn đủ ý nhưng không quá dài."),
    @("So sánh nội bộ", "Trả về nguồn trong corpus có nội dung giống hoặc gần giống, kèm đoạn đang đối chiếu.", "Kết hợp TF-IDF từ, TF-IDF ký tự, shingle n-gram và cosine similarity của embedding."),
    @("Đánh giá trực tuyến", "Quét theo tên sáng kiến, tham khảo 20-30 kết quả đầu và hỗ trợ chấm theo rubric 30/40/30.", "OpenAI API với mô hình GPT, tìm kiếm web, prompt rubric và tổng hợp nguồn tham khảo."),
    @("Báo cáo Word", "Mỗi tài liệu sau khi kiểm tra có một file báo cáo Word riêng để lưu hoặc in.", "python-docx tạo báo cáo; hệ thống ghi rõ điểm tương đồng, đoạn kiểm tra, nguồn đối chiếu và nhận xét."),
    @("Đóng gói chạy máy khác", "Có thể chạy bằng Docker trên máy khác mà không cần cài từng thư viện thủ công.", "Dockerfile, docker-compose, Tesseract tiếng Việt, LibreOffice, Poppler và các thư viện Python được đóng gói.")
)
$body.Add((Table $featureRows))

$body.Add((Para "2.1. Luồng xử lý dữ liệu đầu vào" "Heading2"))
$body.Add((Para "Khi người dùng tải tài liệu lên, hệ thống không dùng OCR ngay từ đầu. OCR thường chậm và có thể sinh lỗi nhận dạng nếu tài liệu vốn đã có lớp chữ thật. Vì vậy app xử lý theo ba lớp ưu tiên:" "Normal" "both"))
$body.Add((Bullet "Lớp 1 - PyMuPDF4LLM: ưu tiên đọc PDF theo cấu trúc gần với tài liệu gốc, giữ được tiêu đề, đoạn văn và thứ tự nội dung."))
$body.Add((Bullet "Lớp 2 - MarkItDown: chuyển đổi các định dạng tài liệu khác nhau sang văn bản thống nhất, đặc biệt hữu ích với DOC, DOCX và một số PDF phức tạp."))
$body.Add((Bullet "Lớp 3 - PyTesseract OCR: chỉ dùng khi hệ thống xác định PDF gần như không có văn bản, thường là file scan hoặc ảnh chụp. OCR được cấu hình tiếng Việt để đọc dấu tốt hơn."))
$body.Add((Para "Nhờ cách xử lý nhiều lớp, phần mềm cân bằng giữa tốc độ, độ chính xác và khả năng đọc tài liệu cũ. Tài liệu có chữ thật sẽ được đọc nhanh; tài liệu scan vẫn có cơ hội được nhận dạng thay vì bị bỏ qua." "Normal" "both"))

$body.Add((Para "2.2. Luồng chunk và embed" "Heading2"))
$body.Add((Para "Sau khi trích xuất văn bản, hệ thống tìm đến đúng phần 'III. Nội dung giải pháp đề nghị công nhận sáng kiến'. Chỉ các mục con thuộc phần này mới được đưa vào đối chiếu, gồm nội dung giải pháp, tính mới - tính sáng tạo, phạm vi ảnh hưởng - khả năng áp dụng và hiệu quả - lợi ích thu được." "Normal" "both"))
$body.Add((Para "Văn bản không bị chia đều một cách máy móc. App ưu tiên giữ nguyên đoạn văn và đầu mục để mỗi đoạn kiểm tra có nghĩa đầy đủ. Nếu một đoạn quá dài, hệ thống mới chia nhỏ theo ranh giới câu. Nếu quá ngắn, hệ thống ghép với đoạn lân cận trong cùng đầu mục để tránh so sánh các mảnh rời rạc." "Normal" "both"))
$body.Add((Para "Mỗi chunk sau đó được đưa qua mô hình embedding tiếng Việt. Có thể hiểu embedding là cách biến một đoạn văn thành một dãy số đại diện cho ý nghĩa của đoạn đó. Nhờ vậy, phần mềm có thể phát hiện hai đoạn gần nghĩa dù không dùng hoàn toàn cùng từ ngữ. Kết quả embedding được lưu trong kho dữ liệu để lần sau kiểm tra nhanh hơn." "Normal" "both"))

$body.Add((Para "2.3. Luồng kiểm tra một hoặc nhiều tài liệu" "Heading2"))
$body.Add((Para "Người dùng có thể tải một tài liệu hoặc nhiều tài liệu cùng lúc. Với từng tài liệu, app đọc nội dung, xác định phần III, chia chunk, tạo embedding, so sánh với kho corpus, tổng hợp kết quả và xuất báo cáo Word riêng. Cách này phù hợp với các đợt nhận nhiều hồ sơ sáng kiến, vì người phụ trách không phải thao tác lặp lại từng file." "Normal" "both"))

$body.Add((Para "2.4. Luồng quét online và chấm rubric" "Heading2"))
$body.Add((Para "Ngoài đối chiếu với kho nội bộ, app có thể dùng tên sáng kiến để chủ động tìm kiếm trực tuyến khoảng 20-30 kết quả đầu tiên. Kết quả tìm được được dùng như nguồn tham khảo khi đánh giá tính mới và khả năng trùng ý tưởng với nội dung công khai trên Internet." "Normal" "both"))
$body.Add((Para "Phần đánh giá theo rubric gồm ba nhóm điểm: Tính mới, tính sáng tạo 30 điểm; Hiệu quả áp dụng, lợi ích thu được 40 điểm; Khả năng nhân rộng 30 điểm. GPT đóng vai trò hỗ trợ tổng hợp, diễn giải và đề xuất điểm theo tiêu chí; quyết định cuối cùng vẫn thuộc người thẩm định." "Normal" "both"))

$body.Add((Para "3. Mục đích" "Heading1"))
$body.Add((Bullet "Giảm thời gian đọc và rà soát thủ công khi số lượng hồ sơ sáng kiến lớn."))
$body.Add((Bullet "Tăng tính khách quan trong bước sàng lọc ban đầu, vì các tài liệu được kiểm tra theo cùng một quy trình."))
$body.Add((Bullet "Phát hiện sớm các đoạn có dấu hiệu tương đồng với sáng kiến đã có trong kho nội bộ."))
$body.Add((Bullet "Hỗ trợ người thẩm định tập trung vào bản chất chuyên môn của giải pháp thay vì mất nhiều thời gian tìm kiếm, sao chép và ghi chú thủ công."))
$body.Add((Bullet "Tạo báo cáo Word rõ ràng, có thể lưu vào hồ sơ, gửi cho tổ thẩm định hoặc dùng làm căn cứ trao đổi lại với tác giả."))

$body.Add((Para "4. Khả năng nhân rộng" "Heading1"))
$body.Add((Para "Giải pháp có khả năng nhân rộng tốt vì chi phí triển khai thấp và không yêu cầu cấu hình máy quá cao. Phần kiểm tra nội bộ có thể chạy hoàn toàn trên máy tính phổ thông, không bắt buộc dùng máy chủ riêng hoặc card đồ họa. Với một máy Windows 10/11, CPU thông thường, RAM khoảng 8-16 GB và ổ cứng còn đủ dung lượng cho kho tài liệu, đơn vị đã có thể sử dụng phần mềm cho quy mô trường học, phòng ban hoặc cụm đơn vị." "Normal" "both"))
$body.Add((Para "Các thư viện chính đều là công cụ mã nguồn mở hoặc có thể dùng miễn phí cho chức năng cục bộ. Mô hình embedding tiếng Việt được lưu ngay trên máy, nên sau khi cài đặt ban đầu, việc đối chiếu nội bộ không phát sinh chi phí theo lượt kiểm tra. Tùy chọn GPT và quét online chỉ cần bật khi đơn vị muốn có thêm đánh giá trực tuyến; đây là phần bổ sung, không phải điều kiện bắt buộc để phần mềm hoạt động." "Normal" "both"))
$body.Add((Para "Việc đóng gói Docker giúp triển khai sang máy khác đơn giản hơn. Người phụ trách chỉ cần cài Docker, sao chép mã nguồn, kho corpus và mô hình local, sau đó chạy container. Cách làm này hạn chế lỗi do khác phiên bản Python, thiếu thư viện OCR hoặc thiếu công cụ chuyển đổi tài liệu." "Normal" "both"))

$body.Add((Para "Điều kiện triển khai đề xuất:" "Heading2"))
$body.Add((Bullet "Máy tính Windows 10/11 hoặc máy chủ nội bộ nhỏ; không cần GPU."))
$body.Add((Bullet "RAM khuyến nghị 8 GB trở lên; 16 GB tốt hơn khi kho tài liệu lớn."))
$body.Add((Bullet "Ổ cứng còn trống tùy theo số lượng PDF/DOCX trong corpus và kích thước mô hình embedding."))
$body.Add((Bullet "Docker Desktop nếu muốn chạy theo container; nếu chạy trực tiếp thì cần Python, Tesseract OCR và các thư viện đi kèm."))
$body.Add((Bullet "Internet chỉ cần thiết khi tải mô hình lần đầu, cài thư viện hoặc sử dụng chức năng quét online/GPT."))

$body.Add((Para "5. Hiệu quả mang lại" "Heading1"))
$body.Add((Para "5.1. Hiệu quả kinh tế" "Heading2"))
$body.Add((Bullet "Giảm chi phí mua hoặc thuê phần mềm kiểm tra tương đồng bên ngoài, đặc biệt khi đơn vị cần kiểm tra định kỳ hằng năm."))
$body.Add((Bullet "Tận dụng máy tính hiện có, không cần đầu tư máy chủ mạnh hoặc hạ tầng phức tạp."))
$body.Add((Bullet "Giảm số giờ công cho khâu rà soát ban đầu. Người phụ trách chỉ cần xem các cảnh báo có độ tương đồng cao thay vì đọc toàn bộ tài liệu từ đầu."))
$body.Add((Bullet "Kho dữ liệu nội bộ càng sử dụng lâu càng có giá trị, vì mỗi sáng kiến đã index sẽ tiếp tục phục vụ các đợt kiểm tra sau."))

$body.Add((Para "5.2. Hiệu quả công việc" "Heading2"))
$body.Add((Bullet "Tốc độ xử lý nhanh hơn khi kiểm tra nhiều hồ sơ, đặc biệt nhờ chức năng tải nhiều tài liệu cùng lúc và xuất báo cáo tự động."))
$body.Add((Bullet "Kết quả dễ theo dõi hơn vì báo cáo thể hiện đúng đoạn văn bản đang kiểm tra và nguồn trong corpus được đối chiếu."))
$body.Add((Bullet "Giảm bỏ sót tài liệu scan nhờ OCR tiếng Việt, đồng thời tránh lạm dụng OCR với tài liệu đã có chữ thật."))
$body.Add((Bullet "Quy trình chấm điểm rõ hơn nhờ rubric 30/40/30, giúp hội đồng có điểm tham khảo ban đầu trước khi đánh giá chuyên môn."))
$body.Add((Bullet "Tính minh bạch tốt hơn: mỗi kết quả có nguồn, đoạn liên quan và điểm tương đồng để người thẩm định kiểm tra lại."))

$body.Add((Para "6. Prompt hoàn chỉnh để hoàn thiện app, chạy được trên máy tính" "Heading1"))
$body.Add((Para "Có thể sử dụng prompt sau với một AI hỗ trợ lập trình để xây dựng hoặc hoàn thiện lại phần mềm trên một máy tính khác. Prompt này mô tả đầy đủ mục tiêu, công nghệ và yêu cầu vận hành." "Normal" "both"))

$prompt = @"
Bạn là kỹ sư phần mềm senior. Hãy xây dựng và hoàn thiện một phần mềm chạy cục bộ để kiểm tra, đối chiếu và hỗ trợ đánh giá hồ sơ sáng kiến kinh nghiệm tiếng Việt.

Mục tiêu chính:
1. Người dùng có thể nạp kho tài liệu sáng kiến cũ vào thư mục corpus.
2. Hệ thống tạo index nội bộ và chỉ index file mới ở các lần chạy sau; có tùy chọn rebuild khi cần làm lại toàn bộ.
3. Người dùng có thể tải lên một hoặc nhiều tài liệu PDF, DOC, DOCX; hệ thống kiểm tra từng tài liệu và xuất một file Word báo cáo riêng cho từng tài liệu.
4. Chỉ đối chiếu từ mục 'III. Nội dung giải pháp đề nghị công nhận sáng kiến' và các mục con III.1, III.2, III.3, III.4. Không dùng phần thông tin chung, tác giả, đơn vị, chữ ký hoặc mục 'II. Mô tả giải pháp đã biết' để tính tương đồng.
5. Báo cáo phải hiển thị đúng đoạn văn bản đang kiểm tra, nguồn trong corpus được đối chiếu, điểm tương đồng và nhận xét dễ hiểu.

Yêu cầu xử lý tài liệu:
- Xây dựng pipeline đọc dữ liệu theo thứ tự ưu tiên: PyMuPDF4LLM, MarkItDown, PyMuPDF, sau đó mới dùng PyTesseract OCR.
- Chỉ OCR khi PDF gần như không có text hoặc text trích xuất quá ít/không đáng tin cậy.
- Cấu hình OCR tiếng Việt và tiếng Anh; ghi lại các file không đọc được cùng lý do.
- Hỗ trợ DOC, DOCX, PDF và TXT/MD nếu có.

Yêu cầu chunk và embedding:
- Viết bộ nhận diện đầu mục tiếng Việt, xử lý Unicode, khoảng trắng, số La Mã và các biến thể như 'III.', 'III.1', 'III.2'.
- Chunk theo đầu mục và ưu tiên đoạn văn tự nhiên; chỉ chia nhỏ khi đoạn quá dài, ghép đoạn khi quá ngắn.
- Mỗi chunk cần lưu metadata: file nguồn, tiêu đề sáng kiến, mục, số thứ tự chunk, nội dung chunk.
- Dùng mô hình sentence-transformers tiếng Việt chạy local, ví dụ thư mục models/vietnamese-sbert.
- Lưu embedding để tìm kiếm nhanh, không tính lại toàn bộ nếu không cần.

Yêu cầu so sánh:
- Kết hợp nhiều tín hiệu: TF-IDF theo từ, TF-IDF theo ký tự, shingle n-gram và cosine similarity của embedding.
- Nếu chưa có embedding thì vẫn chạy được bằng TF-IDF và shingle.
- Tránh so sánh các đoạn hành chính, chữ ký, mẫu biểu, dòng chấm hoặc nội dung quá ngắn.

Yêu cầu đánh giá online:
- Thêm tùy chọn dùng OpenAI API. API key lấy từ biến môi trường OPENAI_API_KEY hoặc file .env, không hard-code trong mã nguồn.
- Dựa trên tên sáng kiến, tự quét 20-30 kết quả online đầu tiên.
- Dùng GPT để tổng hợp và chấm theo rubric: Tính mới, tính sáng tạo 30 điểm; Hiệu quả áp dụng, lợi ích thu được 40 điểm; Khả năng nhân rộng 30 điểm.
- Kết quả GPT chỉ là tham khảo, cần ghi rõ nguồn và lý do chấm.

Yêu cầu giao diện:
- Dùng FastAPI làm backend và giao diện web đơn giản cho người không biết code.
- Có nút kiểm tra một file, kiểm tra nhiều file, tải báo cáo Word, chạy đánh giá online.
- Không hiển thị toàn bộ văn bản corpus; chỉ hiển thị đoạn liên quan khi có kết quả đối chiếu.

Yêu cầu báo cáo:
- Xuất báo cáo Word bằng python-docx cho từng tài liệu.
- Báo cáo gồm thông tin tài liệu, mức tương đồng tổng quan, các đoạn nghi vấn, nguồn đối chiếu, điểm rubric nếu có và khuyến nghị kiểm tra thủ công.

Yêu cầu đóng gói:
- Cung cấp requirements.txt, .env.example, Dockerfile, docker-compose.yml, .dockerignore và hướng dẫn chạy.
- Container cần cài Tesseract OCR với ngôn ngữ tiếng Việt, LibreOffice hoặc công cụ cần thiết để đọc/chuyển đổi tài liệu, Poppler nếu cần xử lý PDF.
- Dữ liệu corpus, data và models phải mount ra ngoài container để dùng lại giữa các lần chạy.

Yêu cầu chất lượng:
- Viết mã rõ ràng, tách module: document_extraction, sectioning, indexer, detector, online_evaluator, reporting, api, cli.
- Có log và thông báo lỗi dễ hiểu.
- Không xóa dữ liệu người dùng khi index tăng dần.
- Kiểm thử tối thiểu các phần: nhận diện mục III, chunk theo đoạn, bỏ qua OCR khi PDF đã có text, index chỉ thêm file mới, và xuất báo cáo Word.
"@
foreach ($line in ($prompt -split "`r?`n")) {
    if ($line.Trim().Length -eq 0) {
        $body.Add((Para "" "Prompt"))
    } else {
        $body.Add((Para $line "Prompt"))
    }
}

$body.Add((Para "Kết luận" "Heading1"))
$body.Add((Para "Phần mềm là một giải pháp thực tế để hỗ trợ rà soát sáng kiến kinh nghiệm trong phạm vi nhà trường, phòng ban hoặc cơ quan chuyên môn. Điểm mạnh của giải pháp nằm ở việc hiểu đúng cấu trúc hồ sơ sáng kiến, tận dụng kho dữ liệu nội bộ, giảm chi phí vận hành và tạo báo cáo rõ ràng. Công cụ không thay thế vai trò của hội đồng thẩm định, nhưng giúp hội đồng có dữ liệu ban đầu nhanh hơn, nhất quán hơn và dễ kiểm tra lại hơn." "Normal" "both"))

$contentTypes = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>
'@

$rels = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
'@

$styles = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/><w:sz w:val="26"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:pPr><w:spacing w:after="200"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:b/><w:sz w:val="32"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle">
    <w:name w:val="Subtitle"/>
    <w:pPr><w:spacing w:after="360"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:i/><w:sz w:val="26"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:keepNext/><w:spacing w:before="260" w:after="120"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:b/><w:sz w:val="30"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:keepNext/><w:spacing w:before="180" w:after="80"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:b/><w:sz w:val="27"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Bullet">
    <w:name w:val="Bullet"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:ind w:left="720" w:hanging="360"/><w:spacing w:after="80"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="26"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Prompt">
    <w:name w:val="Prompt"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:after="60" w:line="240" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="20"/></w:rPr>
  </w:style>
  <w:style w:type="table" w:styleId="TableGrid">
    <w:name w:val="Table Grid"/>
    <w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="888888"/><w:left w:val="single" w:sz="4" w:space="0" w:color="888888"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="888888"/><w:right w:val="single" w:sz="4" w:space="0" w:color="888888"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="888888"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="888888"/></w:tblBorders></w:tblPr>
  </w:style>
</w:styles>
'@

$settings = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:defaultTabStop w:val="720"/>
</w:settings>
'@

$sectPr = '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1134" w:bottom="1134" w:left="1134" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
$document = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + (($body.ToArray()) -join "") + $sectPr + '</w:body></w:document>'

New-Item -ItemType Directory -Path (Join-Path $TempDir "_rels") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $TempDir "word") | Out-Null

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $TempDir "[Content_Types].xml"), $contentTypes, $utf8)
[System.IO.File]::WriteAllText((Join-Path $TempDir "_rels\.rels"), $rels, $utf8)
[System.IO.File]::WriteAllText((Join-Path $TempDir "word\document.xml"), $document, $utf8)
[System.IO.File]::WriteAllText((Join-Path $TempDir "word\styles.xml"), $styles, $utf8)
[System.IO.File]::WriteAllText((Join-Path $TempDir "word\settings.xml"), $settings, $utf8)

if (Test-Path $OutputPath) { Remove-Item -LiteralPath $OutputPath -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($TempDir, $OutputPath)
Remove-Item -LiteralPath $TempDir -Recurse -Force

Write-Output $OutputPath
