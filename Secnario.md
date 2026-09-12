Bốn tài khoản demo được thiết kế để đại diện cho bốn tình huống tài chính khác nhau. Toàn bộ phép tính đang cố định tại ngày demo `01/09/2026`, giúp kết quả trình chiếu ổn định.

## C001 — Nguy cơ thiếu hụt dòng tiền

Khách hàng: Nguyễn Minh An

- Thu nhập tháng: `25.000.000 VND`
- Số dư khả dụng: `9.000.000 VND`
- Mức số dư an toàn: `3.000.000 VND`
- Tiền thuê nhà sắp tới: `6.000.000 VND`, hạn ngày `05/09`
- Chi tiêu gần đây:
  - Mua sắm: `2.750.000 VND`
  - Ăn uống: `1.950.000 VND`

Agent dự báo đến `15/09`:

- Số dư còn khoảng `1.366.667 VND`
- Thấp hơn mức an toàn khoảng `1.633.333 VND`
- Tín hiệu chính: `CASHFLOW_RISK`
- Mức độ: `HIGH`

Agent đề xuất:

- Phương án A: tạo ngân sách `SHOPPING` khoảng `4.000.000 VND`, cảnh báo khi dùng 80%.
- Phương án B: tạo nhắc nhở kiểm tra số dư trước khoản định kỳ.

Khi khách hàng xác nhận:

- Phương án A tạo ngân sách thật trong Mock Core Banking.
- Phương án B tạo reminder thật trong Mock Core Banking.
- Nếu từ chối, không có dữ liệu nào bị thay đổi.

Đây là case tổng quát nhất, phù hợp làm case mở đầu khi demo.

---

## C002 — Chi tiêu ăn uống tăng bất thường

Khách hàng: Trần Thu Hà

- Thu nhập tháng: `32.000.000 VND`
- Số dư khả dụng: `18.500.000 VND`
- Mức số dư an toàn: `5.000.000 VND`
- Mức chi FOOD ba tháng gần nhất:
  - Tháng 6: `4.000.000 VND`
  - Tháng 7: `3.800.000 VND`
  - Tháng 8: `4.200.000 VND`
- Baseline trung bình: `4.000.000 VND`
- Chi FOOD đầu tháng 9: `5.000.000 VND`

Agent phát hiện:

- Chi tiêu ăn uống tăng `25%` so với baseline.
- Tín hiệu chính: `SPENDING_ANOMALY`
- Mức độ: `MEDIUM`

Khách hàng này đã có sẵn ngân sách FOOD:

- Hạn mức: `6.000.000 VND`
- Đã chi: `5.000.000 VND`
- Đã sử dụng: `83,3%`
- Ngưỡng cảnh báo: `80%`

Vì vậy case này thể hiện được cả:

1. Agent so sánh hành vi hiện tại với lịch sử.
2. Agent phát hiện khách hàng đã vượt ngưỡng cảnh báo ngân sách.

Lưu ý về implementation hiện tại: Agent vẫn sinh phương án “Tạo ngân sách FOOD” mới khoảng `5.120.000 VND`. Nếu xác nhận, Core Banking có thể trả lỗi `409` vì đã tồn tại ngân sách FOOD trùng kỳ. Khi demo hiện tại, nên dùng case này để trình bày cảnh báo rồi chọn “Không áp dụng”. Về sau nên sửa action thành “Điều chỉnh ngân sách hiện tại” thay vì tạo mới.

---

## C003 — Mục tiêu tiết kiệm đang chậm tiến độ

Khách hàng: Lê Quang Huy

- Thu nhập tháng: `28.000.000 VND`
- Số dư khả dụng: `12.000.000 VND`
- Mục tiêu: “Home deposit”
- Số tiền mục tiêu: `100.000.000 VND`
- Đã tiết kiệm: `22.000.000 VND`
- Thời gian mục tiêu: `01/05/2026 – 30/04/2027`
- Đóng góp hiện tại: khoảng `8.333.333 VND/tháng`

Tại ngày `01/09/2026`:

- Tiến độ kỳ vọng: khoảng `33,79 triệu VND`
- Tiến độ thực tế: `22 triệu VND`
- Chậm khoảng `11,79 triệu VND`
- Tín hiệu chính: `GOAL_DRIFT`
- Mức độ: `MEDIUM`

Agent đưa ra hai kịch bản:

- Phương án A — Giữ nguyên deadline:
  - Tăng đóng góp lên khoảng `9.750.000 VND/tháng`.
- Phương án B — Giữ mức đóng góp:
  - Gia hạn deadline mục tiêu, dự kiến sang khoảng tháng `07/2027`.

Khi khách hàng xác nhận, Agent gọi API Mock Core Banking để cập nhật trực tiếp mục tiêu tiết kiệm:

- Thay đổi `monthly_contribution`; hoặc
- Thay đổi `target_date`.

Đây là case tốt nhất để thể hiện Agent không chỉ cảnh báo mà còn mô phỏng nhiều phương án và cho khách hàng lựa chọn.

---

## C004 — Khoản định kỳ vượt quá số dư hiện tại

Khách hàng: Phạm Bảo Linh

- Thu nhập tháng: `20.000.000 VND`
- Số dư khả dụng: `7.200.000 VND`
- Mức số dư an toàn: `3.000.000 VND`
- Tiền thuê nhà: `8.000.000 VND`
- Ngày đến hạn: `03/09/2026`
- Còn `2 ngày` đến hạn

Agent xử lý theo chuỗi tín hiệu:

```text
Phát hiện khoản định kỳ
        ↓
UPCOMING_RECURRING
        ↓
Dự báo số dư sau thanh toán = -800.000 VND
        ↓
CASHFLOW_RISK — HIGH
```

Khoản thuê nhà lớn hơn số dư hiện tại `800.000 VND`; sau thanh toán dự kiến:

- Số dư: `-800.000 VND`
- Thấp hơn mức an toàn: `3.800.000 VND`
- Tín hiệu được ưu tiên hiển thị: `CASHFLOW_RISK`
- Mức độ: `HIGH`

Do `CASHFLOW_RISK` có độ ưu tiên cao hơn `UPCOMING_RECURRING`, Agent hiện đề xuất:

- Tạo ngân sách mua sắm để hạn chế chi tiêu tùy ý; hoặc
- Tạo nhắc nhở kiểm tra số dư trước khoản thuê nhà.

Đây là case tốt nhất để trình bày khả năng kết hợp nhiều tín hiệu: Agent không chỉ thấy hóa đơn sắp tới mà còn đánh giá ảnh hưởng của nó lên số dư.

## Thứ tự trình chiếu đề xuất

1. `C001`: demo đầy đủ luồng quét → recommendation → xác nhận → tạo ngân sách.
2. Logout và đăng nhập `C002`: demo phát hiện hành vi chi tiêu bất thường.
3. Chuyển sang `C003`: demo mô phỏng hai phương án điều chỉnh mục tiêu.
4. Chuyển sang `C004`: kết thúc bằng case cross-signal và cảnh báo dòng tiền mức cao.

Lưu ý: MySQL chỉ seed `C001–C004` khi database trống. Những action đã xác nhận ở lần demo trước vẫn còn trong database, nên trạng thái có thể khác seed ban đầu nếu chạy demo nhiều lần.