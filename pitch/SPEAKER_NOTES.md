# Ghi chú trình bày FinSen

Thời lượng mục tiêu: **6 phút 40 giây** cho 11 slide chính. Hai slide phụ lục chỉ dùng khi hỏi đáp. Ghi chú hiện tại nằm trong từng slide web; bản PowerPoint cũ chưa có các slide mới.

## Slide 1: FinSen · 25 giây

25 giây. FinSen là Financial Sensing. Ý tưởng lấy cảm hứng từ nguyên lý sensing trong hỗ trợ lái xe: liên tục quan sát tín hiệu để nhận ra rủi ro sớm. Với tài chính, FinSen giúp khách hàng thấy điều có thể xảy ra tiếp theo và chọn hành động phù hợp. Đây là nguyên mẫu chạy trên dữ liệu ngân hàng giả lập.

## Slide 2: Vấn đề · 35 giây

35 giây. Một app ngân hàng đã có rất nhiều dữ liệu: giao dịch, số dư, lịch trả tiền và mục tiêu. Nhưng khách hàng phải tự ghép các mảnh lại. Có người vẫn thấy tiền trong tài khoản nhưng hai tuần nữa sẽ thiếu. Có người chi tiêu đang tăng mà cuối tháng mới biết. Có người để tiền nhàn rỗi mà chưa nghĩ đến phương án phù hợp. Năm tình huống này có chung một khoảng trống: tín hiệu xuất hiện trước, nhận thức của khách hàng đến sau.

## Slide 3: Insight · 30 giây

30 giây. Sự khác biệt rất đơn giản. Mobile Banking hiện tại kể lại chuyện đã xảy ra. FinSen đặt câu hỏi: từ những dữ liệu đó, điều gì có thể xảy ra tiếp, và khách hàng nên cân nhắc gì ngay bây giờ? FinSen là một lớp cảm nhận đặt trên hành trình ngân hàng hiện có, không yêu cầu khách hàng chuyển sang một công cụ khác.

## Slide 4: Financial Sensing Layer · 35 giây

35 giây. FinSen vận hành theo một chuỗi thống nhất: cảm nhận dữ liệu, phân tích ngữ cảnh, dự báo rủi ro hoặc cơ hội, đề xuất lựa chọn, rồi chỉ thực hiện khi khách hàng quyết định. Ba giá trị là bảo vệ dòng tiền, kiểm soát kế hoạch tài chính và khai thác cơ hội từ nguồn tiền hiện có. Năm case không phải năm tính năng rời rạc mà là năm loại tín hiệu đầu tiên.

## Slide 5: Case C001 dự báo dòng tiền · 55 giây

55 giây. Đây là hero case. Tại mốc fixture ngày 1 tháng 9, C001 có 9 triệu đồng số dư và mức an toàn 3 triệu. Trong kỳ tới có 6 triệu tiền thuê cùng chi tiêu thường lệ. Financial Engine dự báo số dư ngày 15 tháng 9 chỉ khoảng 1,37 triệu, dưới ngưỡng an toàn. Điều đáng nói là hôm nay khách hàng vẫn thấy 9 triệu nên có thể nghĩ mọi thứ ổn. FinSen phát hiện vấn đề trước khi khách hàng trải nghiệm nó. Đề xuất xử lý là một lựa chọn, không phải hành động tự động.

## Slide 6: Năm tín hiệu FinSen · 45 giây

45 giây. Hai case Protect là C001 dự báo thiếu hụt dòng tiền và C004 phát hiện khoản định kỳ có thể vượt số dư. Hai case Control là C002, khi chi ăn uống tăng 25% so với mức nền ba tháng, và C003, khi tiến độ tiết kiệm có nguy cơ chậm. Case Grow là C005: nhận ra nguồn tiền nhàn rỗi và gợi ý sản phẩm theo nhu cầu thực tế. C004 có thể dẫn tới các lựa chọn như bổ sung tiền hoặc giải pháp tín dụng phù hợp, nhưng FinSen không ép khách hàng vay.

## Slide 7: AI Agent và C005 · 45 giây

45 giây. C005 kết lại chuỗi demo bằng một cơ hội tài chính. FinSen thấy số dư thanh toán lớn và ít chi tiêu gần đây nên ban đầu gợi ý xem xét tiết kiệm kỳ hạn 3 hoặc 6 tháng. Khách hàng lo phải dùng tiền đột xuất. Khi có LLM thật, Agent phân loại ý định từ lời nhắn và lịch sử hội thoại, rồi chuyển gợi ý sang M-Sinh lời. Việc kích hoạt vẫn cần thao tác chọn hành động và xác nhận riêng. M-Sinh lời là khoản cho SBSI vay qua nền tảng tích hợp MSB, không phải tiền gửi tiết kiệm MSB. Đoạn hội thoại trên slide được rút gọn để minh họa luồng; ảnh chụp là giao diện demo thật ở trạng thái tài chính ổn định.

## Slide 8: Cách FinSen hoạt động · 40 giây

40 giây. Chỉ cần nhớ bốn lớp. Dữ liệu nghiệp vụ ở Core Banking giả lập. Financial Engine tính các chỉ số và phương án bằng logic xác định. Agent diễn giải, chọn trong phương án hợp lệ và tiếp nhận phản hồi. Trải nghiệm mobile hiển thị cảnh báo, hội thoại và bước xác nhận. Hành động đi qua chính sách, API nghiệp vụ và audit. Chúng tôi đã có các thành phần này trong MVP; chưa kết nối dữ liệu ngân hàng thật.

## Slide 9: Giá trị khách hàng và ngân hàng · 45 giây

45 giây. Giá trị với khách hàng là được cảnh báo sớm, hiểu hành vi và mục tiêu, đồng thời thấy cơ hội từ nguồn tiền đang có. Với ngân hàng, FinSen tạo điểm chạm đúng lúc để hỗ trợ khách hàng và chỉ giới thiệu sản phẩm khi phù hợp. C004 có thể mở ra phương án xử lý dòng tiền, C005 mở ra gợi ý tiết kiệm hoặc M-Sinh lời. Đây là giả thuyết giá trị cho pilot, chưa phải kết quả kinh doanh được đo. Khi thử nghiệm thật, chúng tôi sẽ đo chất lượng tín hiệu, mức quan tâm và tỷ lệ hành động được xác nhận.

## Slide 10: Khác biệt và bước tiếp theo · 40 giây

40 giây. FinSen khác một dashboard ở khả năng dự báo và chủ động. FinSen khác một notification engine ở khả năng lắng nghe và đổi gợi ý theo bối cảnh. FinSen khác một chatbot thuần văn bản ở bước xác nhận, thực hiện và lưu vết. MVP hackathon đã chứng minh luồng trên dữ liệu giả lập. Bước tiếp theo là pilot có kiểm soát, sau đó mới tích hợp dữ liệu và chính sách thật của MSB và mở rộng thêm tín hiệu. Giới thiệu tên thành viên thật khi đã bổ sung vào placeholder. Kết lại: FinSen là Financial Sensing, giúp khách hàng thấy trước, hiểu rõ và tự quyết định.

## Slide 11: Thank you · 5 giây

Cảm ơn ban giám khảo đã lắng nghe. Dừng phần pitch chính tại đây và mời câu hỏi. Hai slide tiếp theo là phụ lục về Tech Stack và kiến trúc hệ thống, chỉ dùng khi cần trao đổi sâu hơn.

## Slide 12: Tech Stack · phụ lục

Giao diện dùng HTML, CSS, JavaScript, được Nginx phục vụ. Các API Core Banking, FinSen Agent và Admin dùng Python 3.11, FastAPI và Pydantic. Core dùng MySQL cloud/RDS, Agent dùng PostgreSQL. Financial Engine tính toán theo quy tắc xác định, LLM chỉ diễn giải và chọn trong phương án hợp lệ. Stack vận hành qua Docker Compose; LLM có chế độ mock và cấu hình GreenNode.

## Slide 13: Kiến trúc triển khai · phụ lục

Năm thành phần hạ tầng gồm một RDS MySQL cho Core Banking và bốn vServer: Core Banking Service cùng Admin Web Control; FinSen Agent cùng Scheduler; PostgreSQL của Agent; và Mobile Banking Simulator. Trình duyệt vào Mobile vServer qua Nginx. Mobile chuyển tiếp API về Core và Agent. Agent gọi Core Banking API qua mạng private để lấy dữ liệu và thực hiện hành động đã xác nhận. Core lưu ở RDS MySQL, Agent lưu tín hiệu, khuyến nghị và log trong PostgreSQL. Scheduler chạy cùng vServer Agent.

