# FinSen Hackathon pitch

Bộ pitch của FinSen được xây dựng dưới dạng web tĩnh tỷ lệ **16:9**, dùng để trình chiếu trực tiếp trong Chrome hoặc Edge. Phiên bản hiện tại gồm **11 slide chính** với thời lượng mục tiêu khoảng **6 phút 40 giây** và **3 slide phụ lục** dùng khi hỏi đáp.

## Thành phần

- `index.html`: nội dung và cấu trúc của 14 slide.
- `styles.css`: giao diện desktop, mobile và các sơ đồ kỹ thuật.
- `slides.js`: điều hướng slide, toàn màn hình và ghi chú thuyết trình.
- `SPEAKER_NOTES.md`: lời nói tham khảo cho phần pitch chính và phụ lục.
- `fonts/`: Be Vietnam Pro Regular, Medium, SemiBold và Bold để trình chiếu offline.
- `assets/`: logo MSB, ảnh chụp sản phẩm, icon case, logo công nghệ và ảnh thành viên.
- `../output/pdf/FinSen_Hackathon_Pitch_2026.pdf`: bản PDF 14 trang đã xuất từ web.

Deck không còn duy trì bản PowerPoint. Mọi cập nhật được thực hiện trên phiên bản web và xuất lại thành PDF khi cần.

## Mở và trình chiếu

Có thể mở trực tiếp `index.html`, hoặc chạy web server từ thư mục gốc dự án:

```powershell
python -m http.server 3001
```

Sau đó mở `http://localhost:3001/pitch/`.

| Phím | Chức năng |
| --- | --- |
| `→`, `Space`, `Enter` | Sang slide tiếp theo |
| `←`, `Backspace` | Quay lại slide trước |
| `F` | Bật hoặc tắt toàn màn hình |
| `N` | Bật hoặc tắt ghi chú thuyết trình |

Deck hỗ trợ thao tác vuốt trên điện thoại. Logo MSB đổi giữa bản màu và bản âm tùy theo nền slide; tên đội `#GenWork` xuất hiện ở góc dưới bên phải.

## Danh sách slide

| # | Chủ đề | Thời lượng |
| --- | --- | ---: |
| 1 | FinSen: Financial Sensing | 25 giây |
| 2 | Problem: dữ liệu có sẵn, tín hiệu bị bỏ lỡ | 35 giây |
| 3 | Insight: từ quá khứ đến điều sắp tới | 30 giây |
| 4 | Solution: Financial Sensing Layer | 35 giây |
| 5 | Hero case C001: dự báo thiếu hụt dòng tiền | 55 giây |
| 6 | Năm tín hiệu dưới ba trụ cột Protect, Control, Grow | 45 giây |
| 7 | Agent experience C005: lắng nghe và đổi gợi ý | 45 giây |
| 8 | How it works: số liệu có căn cứ, hành động có kiểm soát | 40 giây |
| 9 | Business value cho khách hàng và ngân hàng | 45 giây |
| 10 | Khác biệt và lộ trình tiếp theo | 40 giây |
| 11 | Thank you và chuyển sang Q&A | 5 giây |
| 12 | Phụ lục: Tech Stack | Khi cần |
| 13 | Phụ lục: kiến trúc triển khai | Khi cần |
| 14 | Phụ lục: thành viên team #GenWork | Khi cần |

Phần trình bày chính kết thúc ở slide 11. Ba slide sau chỉ mở khi cần giải thích công nghệ, kiến trúc hoặc giới thiệu đội thi.

## Nội dung và thiết kế hiện tại

- Font toàn bộ deck là **Be Vietnam Pro**: Bold hoặc SemiBold cho tiêu đề và key message; Regular hoặc Medium cho nội dung.
- Slide 2 dùng hình minh họa tài khoản để làm rõ việc dữ liệu đã có nhưng tín hiệu vẫn dễ bị bỏ lỡ.
- Slide 3 giữ bố cục so sánh chữ gọn giữa Mobile Banking hiện tại và FinSen.
- Slide 4 dùng nền cam và logo MSB âm bản để nhấn mạnh chuỗi `Sense → Analyze → Predict → Recommend → Action`.
- Slide 5 trực quan hóa C001 bằng số dư hiện tại 9 triệu đồng, ngưỡng an toàn 3 triệu đồng và dự báo ngày 15/09 còn khoảng 1,37 triệu đồng.
- Slide 6 tổng hợp C001–C005 bằng icon nhất quán theo ba nhóm Protect, Control và Grow.
- Slide 7 trình bày C005: Agent nhận biết tiền nhàn rỗi, lắng nghe nhu cầu thanh khoản và đổi gợi ý sang M-Sinh lời.
- Slide 8 sử dụng ảnh `assets/rui_ro_demo_xin.png` và nhấn mạnh hai thông điệp “Số liệu có căn cứ” và “Hành động có kiểm soát”.
- Slide 12 chia công nghệ thành bốn phần: Experience, Core Banking Service, Data, LLM Model + Agent.
- Slide 13 mô tả một VPC, một subnet, bốn vServer và một RDS. Chỉ Mobile Frontend có public endpoint; các service giao tiếp trong mạng nội bộ; FinSen Agent gọi GreenNode MaaS qua HTTPS outbound.
- Slide 14 dùng ảnh tròn cho ba thành viên: Vũ Công Thành, Mai Văn An và Lê Thu Hoài.

## Tech Stack trong phụ lục

| Nhóm | Công nghệ |
| --- | --- |
| Experience | HTML5, CSS3, JavaScript, Nginx |
| Core Banking Service | Python 3.11, FastAPI |
| Data | MySQL/RDS, PostgreSQL |
| LLM Model + Agent | FinSen Agent, Scheduler, Policy Engine, GreenNode MaaS, GLM-5.2 |
| Runtime | Docker Compose |

## Kiến trúc triển khai trong phụ lục

- **vServer 01:** Core Banking Service và Admin Web Control.
- **vServer 02:** FinSen Agent và Scheduler.
- **vServer 03:** PostgreSQL cho dữ liệu FinSen và audit log.
- **vServer 04:** Mobile Frontend chạy Nginx, là điểm vào public duy nhất.
- **RDS MySQL:** lưu dữ liệu nghiệp vụ Core Banking qua private endpoint.
- **GreenNode MaaS:** dịch vụ AI bên ngoài VPC; FinSen Agent chủ động gọi ra bằng HTTPS.

## Thành viên #GenWork

| Thành viên | Đơn vị | Ảnh |
| --- | --- | --- |
| Vũ Công Thành | Khối SI | `assets/avatar/ava1.png` |
| Mai Văn An | Khối Công nghệ | `assets/avatar/ava2.png` |
| Lê Thu Hoài | Khối Công nghệ | `assets/avatar/ava3.png` |

Ảnh thành viên được cắt thành hình tròn bằng CSS. Có thể thay nội dung các file ảnh mà không cần sửa HTML nếu giữ nguyên tên file.

## Dữ liệu và phạm vi demo

- Các số liệu C001 dùng fixture tại ngày **01/09/2026**. Financial Engine dự báo số dư ngày 15/09 là **1.366.667 VND**, được làm tròn thành **1,37 triệu đồng** trên slide.
- C005 minh họa cách FinSen nhận biết số dư nhàn rỗi lớn và gợi ý sản phẩm phù hợp với nhu cầu sử dụng tiền.
- Dữ liệu khách hàng và giao dịch trong demo đều là dữ liệu giả lập; deck không trình bày kết quả từ dữ liệu ngân hàng thật.
- M-Sinh lời trong demo là khoản khách hàng cho SBSI vay qua nền tảng tích hợp với MSB, không phải tiền gửi tiết kiệm tại MSB. Phần pitch chính chỉ trình bày luồng gợi ý và xác nhận; điều kiện sản phẩm chi tiết nằm trong ứng dụng demo.
- Các KPI kinh doanh trên slide 9 là giả thuyết cần đo trong pilot, chưa phải kết quả đã đạt.

## Xuất PDF

Bản PDF tiêu chuẩn nằm tại:

```text
output/pdf/FinSen_Hackathon_Pitch_2026.pdf
```

PDF dùng tỷ lệ 16:9, mỗi slide một trang, có đủ 14 trang và không chứa thanh điều khiển trình chiếu. Khi chỉ thay ảnh thành viên, có thể render lại slide 14 rồi thay trang cuối của PDF để giữ nguyên 13 trang đã kiểm tra trước đó.

## Việc cần chuẩn bị trước khi trình bày

- Kiểm tra ba ảnh trong `assets/avatar/` và cách crop hình tròn trên slide 14.
- Chạy thử case sẽ demo trực tiếp, đặc biệt là C001 và C005.
- Nếu trình diễn C005 bằng hội thoại tự nhiên, cấu hình LLM thật; chế độ mock chỉ dùng cho kiểm thử xác định.
- Xác nhận phạm vi pilot, tiêu chí thành công và chính sách dữ liệu trước khi đưa các nội dung này thành cam kết chính thức.
