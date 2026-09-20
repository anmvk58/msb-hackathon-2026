# FinSen Hackathon pitch

Bản web gồm **11 slide chính** (khoảng **6 phút 40 giây**) và **2 slide phụ lục** để dùng khi hỏi đáp:

- `index.html`: slide web tĩnh, 16:9, mở trực tiếp bằng Chrome hoặc Edge.
- `FinSen_Hackathon_Pitch_v2.pptx`: bản xuất trước đây. Các cập nhật giao diện mới chỉ áp dụng cho bản web.
- `SPEAKER_NOTES.md`: lời nói cho từng slide.

Font Be Vietnam Pro (Regular, Medium, SemiBold, Bold) được lưu trong `fonts/` để trình chiếu offline; giấy phép SIL Open Font License nằm tại `fonts/OFL.txt`.

Chạy web server từ thư mục gốc dự án nếu muốn mở bằng URL:

```powershell
python -m http.server 3001
```

Mở `http://localhost:3001/pitch/`. Phím `→`/`Space` để tiến, `←` để lùi, `F` để toàn màn hình, `N` để xem ghi chú.

## Danh sách slide

| # | Chủ đề | Giây |
| --- | --- | ---: |
| 1 | FinSen: Financial Sensing | 25 |
| 2 | Problem: năm tín hiệu bị bỏ lỡ | 35 |
| 3 | Insight: từ quá khứ sang điều sắp tới | 30 |
| 4 | Solution: Financial Sensing Layer | 35 |
| 5 | Hero case C001: dự báo thiếu hụt dòng tiền | 55 |
| 6 | Năm tín hiệu dưới ba trụ cột Protect, Control, Grow | 45 |
| 7 | Agent experience C005: lắng nghe và đổi gợi ý | 45 |
| 8 | How it works: dữ liệu, engine, agent, trải nghiệm | 40 |
| 9 | Business value cho khách hàng và ngân hàng | 45 |
| 10 | Khác biệt, roadmap, team và closing | 40 |
| 11 | Thank you và chuyển sang Q&A | 5 |
| 12 | Phụ lục: Tech Stack | Khi cần |
| 13 | Phụ lục: kiến trúc 1 RDS và 4 vServer | Khi cần |

Kết thúc phần trình bày chính ở slide 11. Bấm tiến tiếp nếu cần giải thích công nghệ hoặc kiến trúc trong phần hỏi đáp.

## Nội dung cũ được thay đổi

- Slide vấn đề cũ dùng ba case C002/C004/C005 được gộp vào insight chung ở slide 2 và bản đồ tín hiệu ở slide 6. C001 nay là hero case riêng ở slide 5.
- Slide C005 cũ tập trung vào số dư và hai sản phẩm được chuyển thành cuộc đối thoại Agent ở slide 7, để nêu rõ vì sao gợi ý thay đổi.
- Hai slide ảnh chụp Home và FinSen cũ được đưa vào slide 7–8 làm bằng chứng về sản phẩm đang chạy, thay vì chiếm riêng hai slide.
- Slide demo trực tiếp riêng được bỏ để pitch có nhịp 5–7 phút. Người trình bày vẫn có thể mở ứng dụng demo sau phần pitch hoặc trong Q&A.
- Slide kỹ thuật cũ được diễn đạt lại thành luồng nghiệp vụ ở slide 8. FastAPI, Docker và cơ sở dữ liệu không còn là nội dung chính trên sân khấu.

## Dữ liệu cần bổ sung

- **Team:** tên, vai trò và một chuyên môn liên quan của từng thành viên cho placeholder slide 10.
- **Pilot:** phạm vi khách hàng, tiêu chí thành công và chính sách dữ liệu khi MSB phê duyệt. Deck hiện không nêu KPI đã đạt.
- **Demo live:** chọn và thử trước case sẽ trình bày; case C005 cần cấu hình LLM thật để Agent hiểu phản hồi tự nhiên. Chế độ mock chỉ phục vụ kiểm thử xác định.

Các con số C001 là fixture có mốc ngày **01/09/2026**, được ghi trong README dự án. Những tài khoản, giao dịch và kết quả demo khác là dữ liệu giả lập. M-Sinh lời trong C005 là khoản cho SBSI vay qua nền tảng tích hợp MSB, không phải tiền gửi tiết kiệm MSB.

