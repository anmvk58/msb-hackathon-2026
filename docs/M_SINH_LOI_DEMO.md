# Demo C005: tiền nhàn rỗi và M-Sinh lời

1. Trên `http://localhost:3000`, chọn **C005 · Tiền nhàn rỗi / M-Sinh lời** và đăng nhập. Tài khoản thanh toán ban đầu có 30 triệu đồng, hai giao dịch chi nhỏ trong 30 ngày, số dư an toàn 5 triệu đồng.
2. Mở **FinSen** và quét. Agent phát hiện tiền nhàn rỗi, gợi ý cân nhắc tiết kiệm kỳ hạn 3 hoặc 6 tháng. Hai nút này hiện chỉ cho xem xét phương án; demo chưa mở sổ tiết kiệm hoặc báo lãi suất giả định.
3. Trong ô chat bên dưới Action, nhập: **“Nhưng sắp tới tôi có thể sử dụng tiền và mong muốn rút linh hoạt để sử dụng.”** Agent giới thiệu M-Sinh lời, nêu rõ đây là khoản cho SBSI vay, không phải tiền gửi tiết kiệm tại MSB.
4. Chat tiếp **“Tôi đồng ý thực hiện.”** Hai phương án tiết kiệm được thay bằng **Sử dụng M-Sinh lời**. Chọn Action này, nhập mức số dư tối thiểu giữ lại trong tài khoản thanh toán, rồi xác nhận. Agent ghi audit; Mock Core Banking tạo tài khoản M-Sinh lời và chuyển ngay phần vượt ngưỡng. Trang **Tài sản** hiển thị khoản này riêng với tiền gửi tiết kiệm.
5. Từ ngày tiếp theo, scheduler kiểm tra sau 16:00 giờ Việt Nam và chuyển phần vượt ngưỡng tối đa một lần mỗi ngày. Khi tài khoản đã có tiền, có thể rút về tài khoản thanh toán trong trang Tài sản.

FinSen dùng LLM để phân loại ý định theo lời nhắn mới nhất và lịch sử chat thành: tìm hiểu giải pháp linh hoạt, đồng ý dùng M-Sinh lời, hoặc ý định khác. Chỉ kết quả đồng ý mới thay Action; việc kích hoạt vẫn cần thao tác chọn Action và xác nhận riêng. Cần cấu hình `LLM_PROVIDER=greennode` để có nhận diện ngôn ngữ tự nhiên; client `mock` chỉ phục vụ kiểm thử xác định và không giả vờ hiểu hội thoại.

Nội dung sản phẩm được lưu ở `financial-radar-service/app/knowledge/m_sinh_loi.md` và nạp vào prompt chat của Agent. Toàn bộ tài khoản, chuyển tiền và lợi tức trong case này là dữ liệu mô phỏng; demo không tính hoặc cam kết mức lợi tức.
