# Chuẩn Bị Call Với Đức - 2026-04-24

## Mục tiêu buổi call

- Chốt milestone tiếp theo sau khi hoàn thành Phase 1.
- Quyết định xem dự án nên tối ưu trước cho giá trị trong workflow của agent hay mở rộng độ phủ ngôn ngữ.
- Kết thúc buổi call với một kế hoạch thực thi rõ ràng cho 4-6 tuần tới và một chỉ số thành công đã được thống nhất.

## Hiện trạng

- Milestone nền tảng về cơ bản đã xong: hỗ trợ MCP server, truyền kết quả theo session, phản hồi theo token budget, và cache kết quả parse đều đã được triển khai và phản ánh trong roadmap.
- Branch hiện tại tập trung đúng vào phần nền tảng này: MCP adapter, cache, xử lý budget, serialization, test, và tài liệu.
- Sản phẩm hiện đã có chiều sâu khá tốt về phân tích kiến trúc: parsing, recovery, smell detection, metrics, comparison, và visualization cho Java, Python, và C/C++.
- Khoảng trống lớn nhất lúc này là sản phẩm vẫn mang tính tool-centric nhiều hơn agent-task-centric.

## Đã có gì và còn thiếu gì

### Giá trị đã có

- Phần lõi phân tích kiến trúc đã tương đối đầy đủ.
- Tích hợp MCP giúp các tool có thể được gọi từ agent bên ngoài.
- Token budgeting và caching giúp việc dùng lặp lại trong workflow của agent trở nên thực tế hơn.

### Giá trị còn thiếu

- Chưa có workflow summarize, nên agent vẫn phải gọi nhiều tool để tự định hướng codebase.
- Chưa có hierarchical drill-down, nên chưa hỗ trợ tốt việc đi từ overview của repo xuống package, component, hoặc cụm file cụ thể.
- Chưa có explain_component, context_for_task, hoặc diff_impact, trong khi đây là các tính năng có khả năng biến sản phẩm thành công cụ dùng hằng ngày.
- Hỗ trợ TypeScript hiện vẫn chỉ ở mức stub, làm giảm khả năng áp dụng với các repo thiên về web.

## Lộ trình đề xuất để thảo luận

### Milestone A: MVP định hướng cho agent

Mục tiêu thời gian: 1-2 tuần tới.

- Xây summarize thành entry point chính cho agent.
- Trả về top-level modules, các component quan trọng, dependency hotspots, entry points, và một bản tóm tắt kiến trúc gọn.
- Hỗ trợ drill-down theo focus để một lệnh summary có thể thu hẹp xuống package, component, hoặc nhóm file cụ thể.

Tiêu chí hoàn thành:

- Agent có thể hiểu repository này chỉ sau 1-2 lần gọi tool thay vì phải đọc quá nhiều file.
- Chất lượng output đủ tốt để hỗ trợ các tác vụ tiếp theo như debug, review, hoặc lập kế hoạch.

### Milestone B: Chọn ngữ cảnh theo tác vụ

Mục tiêu thời gian: 1-2 tuần tiếp theo.

- Thêm explain_component.
- Thêm context_for_task.
- Giữ scope gọn, tập trung vào relevance ranking và mô tả vai trò ngắn, rõ ràng.

Tiêu chí hoàn thành:

- Khi đưa vào một mô tả task, tool có thể đề xuất bộ file tối thiểu nhưng hữu ích để đọc.
- Một component có thể được giải thích theo cách hữu ích cho agent hoặc reviewer, không chỉ dừng ở metadata cấu trúc.

### Milestone C: Hiểu thay đổi theo ngữ cảnh

Mục tiêu thời gian: triển khai sau khi Milestone B chứng minh được giá trị.

- Thêm diff_impact.
- Sau đó cân nhắc changelog_architecture nếu workflow PR và release thực sự cho thấy nhu cầu.

Tiêu chí hoàn thành:

- Một PR hoặc git diff có thể được ánh xạ sang các component bị ảnh hưởng và rủi ro downstream.

## Đề xuất ưu tiên

- Ưu tiên summarize và drill-down trước khi làm TypeScript parser.
- Lý do: dự án đã có nền tảng kỹ thuật tốt, nhưng vẫn thiếu một workflow đủ mạnh để trở thành killer use case cho agent.
- Chỉ nên đẩy TypeScript lên ưu tiên cao hơn nếu nhóm người dùng mục tiêu trước mắt là web hoặc full-stack.

## Các quyết định cần chốt với Đức

- Người dùng chính của milestone tiếp theo là ai: AI coding agents, architecture reviewers, hay nhóm nghiên cứu/demo?
- Chỉ số thành công tiếp theo nên xoay quanh tiết kiệm token, rút ngắn thời gian onboarding repo, cải thiện ngữ cảnh review PR, hay mức độ adoption bên ngoài?
- MVP của summarize nên giữ ở mức thuần cấu trúc, hay nên thêm luôn git hotspots và public API hints ngay từ đầu?
- TypeScript support có nên tiếp tục ở tier sau, hay cần làm song song vì nhu cầu thị trường?
- Dự án nên tiếp tục đi theo hướng library-first với adapters, hay bắt đầu đóng gói một trải nghiệm agent hoàn chỉnh hơn ngay từ đầu?

## Rủi ro cần nêu rõ

- Roadmap có thể tiếp tục đi sâu vào hạ tầng nhưng vẫn không tạo ra được workflow thực sự phải dùng cho agent.
- Việc TypeScript vẫn là stub có thể chặn khả năng dùng trên một nhóm lớn repository hiện đại.
- Hiện chưa có evaluation harness đủ rõ để đo xem output có thực sự giúp agent làm task tốt hơn hay không.
- Cache artifacts có thể xuất hiện trong working tree khi dùng local, gây nhiễu nếu không được quản lý hoặc ignore cẩn thận.

## Agenda gợi ý cho 30 phút

- 5 phút: nhắc lại hướng sản phẩm và những gì Phase 1 đã hoàn thành.
- 10 phút: chọn milestone tiếp theo và chốt một chỉ số thành công chính.
- 10 phút: chốt scope cho summarize MVP và những gì chủ động chưa làm.
- 5 phút: phân công người phụ trách, timeline, và checkpoint follow-up.

## Kết luận đề xuất khi chốt call

- Chốt Milestone A là milestone ưu tiên ngay bây giờ.
- Định nghĩa một MVP gọn cho summarize kèm drill-down.
- Hoãn việc mở rộng thêm cho đến khi nhóm xác thực được rằng agent thực sự định hướng repo tốt hơn với ít context hơn.