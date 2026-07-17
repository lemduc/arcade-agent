# Tóm Tắt Cuộc Họp: Đức Lê - Chiến Lược Agent

Ngày: 2026-06-11
Người tham gia: Tuấn Nguyễn, Đức Lê
Nguồn: transcript xuất từ TranscripTonic

## Tóm Tắt Nhanh

Cuộc trao đổi tập trung vào 3 nhóm vấn đề chính:

1. Bối cảnh doanh nghiệp Việt Nam, đặc biệt là mô hình công ty công nghệ nội bộ sau khi tách khỏi tập đoàn lớn.
2. Hướng phát triển cho `arcade-agent`: giúp tích hợp nhanh vào các repo/CI, đóng gói như skill/MCP/action, và có thể dùng làm nền tảng cho research/industry paper.
3. Cơ hội tư vấn, training, và agent cho doanh nghiệp Việt Nam, đặc biệt xoay quanh IAM, data governance, BI agent, security, và phân quyền truy cập dữ liệu.

## Ý Chính

### 1. Bối Cảnh Công Ty Và Thị Trường Việt Nam

- Đức chia sẻ về việc các công ty công nghệ nội bộ trong tập đoàn lớn mới tách thành doanh nghiệp riêng, nên vẫn đang trong giai đoạn chuyển đổi về cơ cấu, cách hạch toán, và cách các đơn vị nội bộ trả tiền cho dịch vụ IT.
- Văn hóa vận hành có áp lực cao: nhiều họp, yêu cầu từ cấp trên nhanh, sự cố cần tìm nguyên nhân và báo cáo rất sớm.
- Security và verification đang được đẩy lên mức ưu tiên cao. Có nhắc đến các sự cố liên quan tới giả mạo/hacker và việc nhận diện sai người/ngữ cảnh.
- Việt Nam có nhu cầu lớn về tư vấn thực chiến, nhưng việc bán hàng và thực thi phụ thuộc nhiều vào quan hệ, network, và khả năng nối kinh nghiệm quốc tế với bài toán trong nước.

### 2. Hướng Cho `arcade-agent`

- Mục tiêu gần là làm sao để các repo khác tích hợp `arcade-agent` nhanh nhất có thể, thay vì phải thao tác thủ công nhiều.
- Các kênh phân phối được nhắc tới:
  - GitHub Action/composite action cho CI.
  - MCP để agent/tool khác gọi trực tiếp.
  - Codex/agent skill để ép agent follow một architecture hoặc workflow nhất định trước khi build.
  - Hướng dẫn setup ngắn gọn để người dùng marketing/adoption dễ hiểu.
- Đức nhắc đến ý tưởng viết một paper ngắn, khoảng 4-6 trang, theo hướng ứng dụng:
  - Agent có skill/architecture instruction trước khi build.
  - So sánh kết quả có và không có skill.
  - Đo validation bằng cách chạy nhiều lần, ví dụ 20 lần, để xem tỉ lệ thành công/lỗi khi agent làm task.
- Có thể target các track paper/industry paper vào khoảng tháng 9-10, vì deadline gần cuối tháng này có vẻ quá gấp.

### 3. Ý Tưởng Research/Validation

- Giả thuyết: khi agent được nạp trước skill/context architecture, kết quả build/refactor sẽ ổn định và đúng hướng hơn.
- Cách validate được thảo luận:
  - Chạy cùng một task nhiều lần với hai cấu hình: có skill và không có skill.
  - Ghi nhận tỉ lệ thành công, lỗi truy cập, lỗi architecture, lỗi test/build.
  - So sánh chất lượng đầu ra theo các tiêu chí có thể đo được.
- Ý tưởng này hợp với `arcade-agent` vì tool có thể dùng để phân tích architecture, smell, metric, và drift sau mỗi lần agent sinh code.

### 4. Cơ Hội Consulting/Training

- Đức đang nghĩ tới việc mở rộng network và làm consulting theo mô hình chuyên gia thực chiến, không nhất thiết full-time.
- Một số hướng có thể có nhu cầu:
  - IAM/identity cho doanh nghiệp Việt Nam.
  - Cybersecurity awareness/training, có liên quan tới các dự án đào tạo bảo vệ trên không gian mạng.
  - Agent/BI cho doanh nghiệp: sếp hỏi trực tiếp về doanh số, tài chính, vận hành, sản phẩm bán chạy, rủi ro.
  - Data governance: tài liệu nào dùng chung, tài liệu nào theo phòng ban, dữ liệu nào được share giữa các đơn vị.
- Tuấn chia sẻ đã từng làm agent/internal workflow cho một công ty Việt Nam, nhận thấy vấn đề lớn nằm ở quản trị dữ liệu và quy trình, không chỉ ở công nghệ.

### 5. Enterprise Agent, IAM, Và Data Governance

- Bài toán enterprise agent không chỉ là LLM trả lời câu hỏi, mà còn phải gắn với:
  - Quyền truy cập của từng người dùng.
  - Phân cấp dữ liệu theo vai trò/phòng ban/công ty con.
  - Hợp đồng và ranh giới chia sẻ dữ liệu giữa các đơn vị.
  - Audit, security, và compliance.
- Ví dụ được nhắc tới: sếp có quyền rộng hỏi agent về dữ liệu toàn công ty, nhân viên chỉ được hỏi trong phạm vi dữ liệu nhỏ hơn.
- Với tập đoàn lớn, có thể có bài toán kết nối identity và dữ liệu khách hàng giữa Vinhome, Vinpearl, VinFast, Vinmec... để hỗ trợ bán chéo, nhưng cần xử lý cẩn thận về giấy tờ, hợp đồng, và quyền sử dụng data.

## Cơ Hội

- Dùng `arcade-agent` như một công cụ validation cho agent-generated code:
  - Kiểm tra architecture drift.
  - Đo metric chất lượng architecture.
  - So sánh kết quả giữa các agent/workflow khác nhau.
- Đóng gói `arcade-agent` thành một adoption path rất ngắn:
  - Copy workflow vào repo.
  - Chọn version/action.
  - Chạy report trên PR.
  - Có optional MCP/skill cho agent automation.
- Viết paper ngắn theo hướng industry/research:
  - "Architecture-aware coding agents through executable skills and architecture analysis".
  - Evidence dựa trên repeated runs và metric từ `arcade-agent`.
- Mở rộng sang consulting/training:
  - Agent readiness assessment.
  - IAM/data governance assessment cho AI/BI agent.
  - Security/verification training.

## Rủi Ro / Câu Hỏi Mở

- Cần làm rõ metric nào dùng để đánh giá agent output: pass test, build success, architecture smell, drift, maintainability, security issue, hay human review score.
- Cần chọn task validation vừa đủ nhỏ để lặp lại nhiều lần, vừa đủ thực tế để có giá trị cho paper/marketing.
- Nếu làm enterprise agent cho BI/IAM, cần tách rõ phần công nghệ LLM với phần data governance, permission model, audit, và legal contract.
- Thị trường enterprise AI bị các nền tảng lớn như Microsoft, Google, Salesforce, Databricks cạnh tranh mạnh; cơ hội tốt hơn có thể nằm ở bài toán địa phương, data trong nước, security, identity, và integration với hệ thống sẵn có.

## Việc Nên Làm Tiếp

1. Chốt một experiment nhỏ cho `arcade-agent`:
   - Chọn 1-2 repo/task mẫu.
   - Chạy agent với/không với skill architecture.
   - Lặp lại nhiều lần và ghi metric.

2. Định nghĩa scoring/validation:
   - Build/test pass rate.
   - Architecture smell count.
   - Architecture drift score.
   - Balanced architecture score nếu phù hợp.
   - Manual review notes cho các lỗi không đo được tự động.

3. Làm adoption package ngắn:
   - README section cho GitHub Action.
   - Example workflow.
   - MCP/skill usage note.
   - Một demo report để người mới thấy giá trị nhanh.

4. Phác thảo paper 4-6 trang:
   - Problem: coding agents không ổn định về architecture.
   - Approach: nạp skill/context + dùng `arcade-agent` để validate.
   - Experiment: repeated runs.
   - Result: metric và observation.
   - Discussion: ứng dụng trong CI và enterprise engineering workflow.

5. Tiếp tục trao đổi với Đức về:
   - Use case IAM/enterprise BI agent nào có dữ liệu thật để validate.
   - Track paper/industry conference phù hợp vào tháng 9-10.
   - Cơ hội training/consulting nào có thể test market trước.
