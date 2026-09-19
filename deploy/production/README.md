# Triển khai trên 5 hạ tầng

Các file này tách stack local hiện tại thành 4 bộ Docker Compose, chạy trên 4
server ứng dụng/DB; MySQL cloud là dịch vụ đã có sẵn. `docker-compose.yml` ở
gốc repo tiếp tục phục vụ phát triển local.

> **Phạm vi hiện tại:** đây là bản demo với dữ liệu giả lập. Mobile dùng
> `demo-login`; Core Banking API và Agent API chưa có xác thực người dùng,
> phân quyền theo khách hàng. Admin CRUD cũng chưa có đăng nhập. Không kết nối
> dữ liệu ngân hàng thật hoặc mở trực tiếp các API này ra Internet cho khách
> hàng trước khi bổ sung các kiểm soát đó.

## Sơ đồ kết nối

| Máy | Container | Cổng nhận | Chỉ cho phép từ |
| --- | --- | --- | --- |
| Cloud MySQL | DB Core Banking | 3306 (hoặc cổng provider) | Core Banking server |
| Core Banking server | `corebanking` | IP private:8090 | Agent server, Mobile server |
| Core Banking server | `core-banking-admin` | `ADMIN_BIND_IP`:8100 (mặc định 0.0.0.0) | Máy có thể kết nối tới Core server |
| PostgreSQL server | `financial-radar-db` | IP private:5432 | Agent server |
| Agent server | `financial-radar-agent` | IP private:8080 | Mobile server |
| Agent server | `financial-radar-scheduler` | Không mở cổng | Core API, PostgreSQL, LLM |
| Mobile server | `frontend-mobile` | 0.0.0.0:80 mặc định | Trình duyệt qua IP public |

Các IP private mẫu trong file `.env.example` phải được thay bằng IP thực.
Thiết lập security group/firewall tương ứng; không mở MySQL, PostgreSQL,
Core API hoặc Agent API cho Internet. Mobile là điểm vào duy nhất của trình
duyệt. Mobile mặc định nghe trên cổng 80 của mọi IPv4 interface để truy cập
qua `http://IP_PUBLIC_MOBILE_SERVER`. Cho phép TCP 80 ở firewall/security
group. Ba đường kết nối máy với máy nên nằm trên mạng private/VPN; áp dụng
TLS cho DB/API nếu đi qua mạng không tin cậy.

## Chuẩn bị chung

1. Cài Docker Engine và Compose plugin trên mỗi server tự quản lý. Copy/clone
   cùng một commit repo lên 4 server. Không copy file `.env` local lên server.
2. Trên từng server, copy đúng file `.env.example` thành `.env` tương ứng trong
   `deploy/production/`, điền địa chỉ và thông tin xác thực thực. Ví dụ:

   ```bash
   cp deploy/production/core.env.example deploy/production/core.env
   chmod 600 deploy/production/core.env
   ```

   Làm tương tự cho `agent-db.env`, `agent.env`, `mobile.env` trên server của
   chúng. Các file `.env` thực đã bị Git bỏ qua. Không đưa mật khẩu hoặc API
   key vào Git, log, hay câu lệnh shell dùng chung.
3. Trong URL SQLAlchemy, ký tự đặc biệt của mật khẩu phải được URL-encode.
   Cloud MySQL phải cho phép kết nối từ IP của Core server. Tạo database/user
   với quyền cần thiết. Bật TLS theo chính sách của nhà cung cấp MySQL.
4. Nếu chạy với `LLM_PROVIDER=greennode`, điền `LLM_BASE_URL`, `LLM_MODEL`,
   `LLM_API_KEY` trên Agent server. `AGENT_RUNTIME=local` nghĩa là runtime
   tự host trên server, vẫn có thể gọi GreenNode LLM.

## Thứ tự khởi động

Các lệnh chạy từ thư mục gốc repo trên **đúng server**. `--env-file` cấp biến
cho Docker Compose; `env_file` trong Compose cấp biến cho container.

### 1. Cloud MySQL

Tạo DB `corebanking` và user cho Core Banking; xác nhận Core server kết nối
được. Tránh dùng tài khoản root. Ghi lại endpoint private và yêu cầu TLS.

### 2. PostgreSQL server

```bash
docker compose --env-file deploy/production/agent-db.env -f deploy/production/agent-db.compose.yml up -d
docker compose --env-file deploy/production/agent-db.env -f deploy/production/agent-db.compose.yml ps
```

Volume `financial-radar-postgres-data` giữ dữ liệu qua lần rebuild. Sao lưu
PostgreSQL định kỳ, kiểm tra khôi phục và đặt quy tắc retention phù hợp.

### 3. Core Banking server

```bash
docker compose --env-file deploy/production/core.env -f deploy/production/core.compose.yml up -d --build
docker compose --env-file deploy/production/core.env -f deploy/production/core.compose.yml ps
curl -fsS http://YOUR_CORE_PRIVATE_IP:8090/health
curl -fsS http://127.0.0.1:8100/health
```

Core API hiện tự chạy `metadata.create_all()` lúc khởi động. Việc này tạo
bảng khi DB trống nhưng **không cập nhật schema của bảng đã tồn tại**. Trước
mỗi bản phát hành có thay đổi schema, cần migration được kiểm duyệt và backup
DB; không dựa vào `create_all()` để thay cột. `CORE_BANKING_SEED_DEMO_ON_START`
mặc định là `false` ở cấu hình này. Chỉ đặt `true` khi chủ ý nạp dữ liệu demo
vào DB trống.

Admin mặc định nghe trên mọi IPv4 interface (`ADMIN_BIND_IP=0.0.0.0`).
Mở TCP 8100 trong firewall/security group của Core server rồi truy cập
`http://IP_PUBLIC_CORE_SERVER:8100`. Có thể thay `ADMIN_BIND_IP` bằng một IP
cụ thể của server nếu chỉ muốn nghe trên interface đó. Admin hiện không có
đăng nhập; bất kỳ ai kết nối được cổng 8100 đều có quyền quản trị dữ liệu demo.

### 4. Agent server

```bash
docker compose --env-file deploy/production/agent.env -f deploy/production/agent.compose.yml up -d --build
docker compose --env-file deploy/production/agent.env -f deploy/production/agent.compose.yml ps
curl -fsS http://YOUR_AGENT_PRIVATE_IP:8080/health
docker compose --env-file deploy/production/agent.env -f deploy/production/agent.compose.yml logs --tail=50 financial-radar-scheduler
```

Agent tạo bảng của nó bằng `create_all()` lúc khởi động với cùng giới hạn
migration như Core. Chỉ chạy **một** scheduler mặc định. Scheduler lấy danh
sách khách hàng từ Core API, quét theo chu kỳ và gọi sweep M-Sinh lời sau
16h giờ Việt Nam. Cấu hình `SCHEDULER_INTERVAL_SECONDS` trong `agent.env`.

### 5. Mobile server

```bash
docker compose --env-file deploy/production/mobile.env -f deploy/production/mobile.compose.yml up -d --build
docker compose --env-file deploy/production/mobile.env -f deploy/production/mobile.compose.yml ps
curl -fsS http://127.0.0.1/health
```

Ảnh production của Mobile dùng Nginx template để route `/api/core/` và
`/api/agent/` tới hai server private. URL API không nằm trong JavaScript
public. Proxy Mobile chặn `/api/core/api/admin/`. Truy cập qua IP public bằng
`http://IP_PUBLIC_MOBILE_SERVER` mà không cần ghi cổng trong URL.

## Kiểm tra sau triển khai

Từ Mobile server, kiểm tra `/health` của hai upstream qua IP private. Sau
khi HTTPS hoạt động, kiểm tra trên domain Mobile:

```bash
curl -fsS https://mobile.example.com/health
curl -fsS https://mobile.example.com/api/core/health
curl -fsS https://mobile.example.com/api/agent/health
```

Thử đăng nhập tài khoản demo, quét Agent, chọn một action và xác nhận; xem
Admin, log Core/Agent và dữ liệu DB để đối chiếu. API Admin qua đường Mobile
phải trả 404. Lưu ý các health endpoint hiện chỉ kiểm tra web process; để
giám sát production cần thêm kiểm tra phụ thuộc, log tập trung và cảnh báo.

## Cập nhật và rollback

Pin cùng một Git commit (hoặc image tag bất biến) trên cả 4 server. Backup
MySQL/PostgreSQL trước bản phát hành có thay đổi schema. Build và cập nhật
theo thứ tự DB migration → Core → Agent → Mobile; kiểm tra health và luồng
nghiệp vụ sau từng bước. Khi rollback code, bảo đảm migration tương thích với
bản code cũ; không tự động xóa volume. Stack local vẫn dùng:

```bash
docker compose up -d --build
```

## Những việc bắt buộc trước khi phục vụ khách hàng thật

- Thay `demo-login` bằng xác thực thật; kiểm tra chủ sở hữu `customer_id` ở
  mọi Core/Agent endpoint và cấp quyền riêng cho Admin, Agent, Mobile.
- Bảo vệ API nội bộ bằng service identity/mTLS hoặc cơ chế tương đương; giới
  hạn đường API được Mobile public. Hiện một người biết URL có thể gọi API
  demo trực tiếp dù không dùng giao diện.
- Thêm migration versioned, backup/restore được diễn tập, quản lý secret,
  audit, giám sát và chính sách retention.
- Rà soát pháp lý/nghiệp vụ cho M-Sinh lời; triển khai tích hợp thực với Core
  Banking/SBSI thay cho hạch toán demo hiện tại.
