# Setup day — connecting the attendance machines to Payobook

For the HR and IT team on the day the machines are connected. No technical
knowledge needed. Vietnamese below (**Tiếng Việt ở phía dưới**).

Your Payobook address: **sudima.payobook.com**

Pick a quiet day — not the first or last days of the month — and an hour when
nobody needs to punch in or out (after 15:00 is good). Have one person at the
machine and one person at a computer with Payobook open at
**Time › Time clocks**.

---

## English

### Before you start

- Payobook open on a computer: **Time › Time clocks**. Keep this screen open.
- The machine's admin (menu) password, if it has one.
- Nothing changes for the attendance program on the office PC. It keeps
  working as it does today, side by side.

### On each machine

The menus look the same on both models; only the colours differ.

| Model | Menu colour |
|---|---|
| 4000TID-C | orange |
| FA110 | green |

1. Press **Menu** (sign in as admin if asked).
2. Open **Comm.** and then **Cloud Server** (on a Vietnamese menu:
   **Cài đặt máy chủ đám mây**).
3. Set it exactly like this:

   | Setting | Set to |
   |---|---|
   | Server type | **ADMS** |
   | Enable domain name | **ON** |
   | Server address | **sudima.payobook.com** |
   | Server port | **443** |
   | Proxy server | **OFF** |
   | HTTPS | **ON** |

   If the machine refuses the address, type it as
   **https://sudima.payobook.com** instead.
4. Press **Save**, then **restart the machine** (Menu › System › Restart, or
   turn it off and on).

### What you see in Payobook

5. **Within a minute** the machine appears at the top of the Time clocks
   screen under **"Machines asking to connect"**, with its serial number.
6. Press **Allow**. Fill in four things:
   - **Name** — what people call it, for example "Factory 2 gate".
   - **Location** — the workshop or building.
   - **Time zone** — Asia/Ho_Chi_Minh.
   - **Pair punches from** — the first day of the current pay month (it is
     filled in for you).
7. Press **Let it in**.
8. The machine now sends everything it still holds. In a minute or two its
   card shows **"Connected"**, today's punches, and a line like
   *"Pairing from 01 Dec 2026 · 12,400 older punches kept, not paired"* —
   older punches are kept on record but never become work days.
9. Ask one person to punch on that machine. Their punch appears in
   **Recent punches** within a few seconds, and the hours show in the Week
   Grid in the next minutes.

### If the machine does not appear after 5 minutes

- Check the machine is on the network (the same cable or Wi-Fi it uses for
  the attendance program).
- Check every setting in the table above again, save, restart.
- Still nothing? Some older machines cannot make a secure connection. Ask
  Payobook to switch on **"Allow a plain connection"** for your company, then
  on the machine set **HTTPS: OFF** and **Server port: 80**, save and restart
  again. Only the number on the machine, the time and the machine's serial
  travel this way — never a fingerprint or a face.

### Every machine, every number

- Each person's number on the machine must be their employee code in
  Payobook. A number that matches nobody shows under **"Numbers that match
  nobody"** — type a name and press Enter, and everything that number punched
  is counted at once.
- A machine you do not recognise asking to connect? Press **Ignore**.

### History from the attendance program

If you also want the days before the pay month began, export the attendance
program's daily sheet to Excel and upload it at **Time › Import ›
Time-clock punches**. Punches already in Payobook are kept once.

### Printable checklist

1. ☐ Payobook open at Time › Time clocks
2. ☐ Machine: Menu › Comm. › Cloud Server
3. ☐ Server type ADMS, Enable domain name ON
4. ☐ Address sudima.payobook.com, port 443
5. ☐ Proxy OFF, HTTPS ON
6. ☐ Save and restart the machine
7. ☐ Machine appears under "Machines asking to connect" → Allow
8. ☐ Name, location, time zone, pair-from day → Let it in
9. ☐ One person punches → it shows in Recent punches
10. ☐ Repeat for the next machine (seven in all)

---

## Tiếng Việt

### Trước khi bắt đầu

- Mở Payobook trên máy tính: **Thời gian › Máy chấm công**. Giữ màn hình này mở.
- Mật khẩu quản trị (menu) của máy chấm công, nếu có.
- Chương trình chấm công trên máy tính văn phòng không thay đổi gì. Nó vẫn
  chạy song song như hôm nay.

### Trên từng máy chấm công

Menu của hai loại máy giống nhau; chỉ khác màu.

| Loại máy | Màu menu |
|---|---|
| 4000TID-C | cam |
| FA110 | xanh lá |

1. Nhấn **Menu** (đăng nhập quản trị nếu máy hỏi).
2. Mở **Comm.** (Truyền thông), rồi **Cài đặt máy chủ đám mây**.
3. Cài đặt đúng như sau:

   | Mục | Chọn |
   |---|---|
   | Loại máy chủ | **ADMS** |
   | Bật tên miền | **BẬT** |
   | Địa chỉ máy chủ | **sudima.payobook.com** |
   | Cổng máy chủ | **443** |
   | Máy chủ proxy | **TẮT** |
   | HTTPS | **BẬT** |

   Nếu máy không nhận địa chỉ, hãy gõ **https://sudima.payobook.com**.
4. Nhấn **Lưu**, rồi **khởi động lại máy** (Menu › Hệ thống › Khởi động lại,
   hoặc tắt rồi bật lại).

### Trên Payobook

5. **Trong vòng một phút**, máy xuất hiện ở đầu màn hình Máy chấm công, trong
   mục **"Máy đang xin kết nối"**, kèm số sê-ri.
6. Nhấn **Cho phép**. Điền bốn mục:
   - **Tên** — tên mọi người hay gọi, ví dụ "Cổng Xưởng 2".
   - **Vị trí** — xưởng hoặc tòa nhà.
   - **Múi giờ** — Asia/Ho_Chi_Minh.
   - **Ghép lượt chấm từ ngày** — ngày đầu tiên của tháng lương hiện tại (đã
     được điền sẵn).
7. Nhấn **Cho kết nối**.
8. Máy sẽ gửi toàn bộ dữ liệu còn lưu. Sau một hai phút, thẻ của máy hiện
   **"Đã kết nối"**, số lượt chấm hôm nay, và một dòng như *"Ghép từ
   01/12/2026 · 12.400 lượt chấm cũ được lưu, không ghép"* — lượt chấm cũ
   được lưu lại nhưng không bao giờ thành ngày công.
9. Nhờ một người chấm công trên máy đó. Lượt chấm hiện trong **Lượt chấm gần
   đây** sau vài giây, và giờ làm hiện trong Lưới tuần vài phút sau.

### Nếu sau 5 phút máy vẫn chưa xuất hiện

- Kiểm tra máy có kết nối mạng (cùng dây mạng hoặc Wi-Fi mà chương trình
  chấm công đang dùng).
- Kiểm tra lại từng mục trong bảng trên, lưu, khởi động lại.
- Vẫn không được? Một số máy đời cũ không tạo được kết nối bảo mật. Hãy nhờ
  Payobook bật **"Cho phép kết nối thường"** cho công ty, rồi trên máy chọn
  **HTTPS: TẮT** và **Cổng máy chủ: 80**, lưu và khởi động lại. Theo cách này
  chỉ có số trên máy, thời gian và số sê-ri của máy được gửi đi — không bao
  giờ có vân tay hay khuôn mặt.

### Mỗi máy, mỗi mã số

- Mã số của mỗi người trên máy chấm công phải là mã nhân viên của họ trên
  Payobook. Mã số không khớp với ai sẽ hiện trong **"Mã chưa khớp với
  ai"** — gõ tên rồi nhấn Enter, mọi lượt chấm của mã đó được tính ngay.
- Có máy lạ xin kết nối? Nhấn **Bỏ qua**.

### Dữ liệu cũ từ chương trình chấm công

Nếu cần cả những ngày trước đầu tháng lương, hãy xuất bảng chấm công hằng ngày
của chương trình ra Excel và tải lên tại **Thời gian › Nhập › Lượt chấm từ máy
chấm công**. Lượt chấm đã có trên Payobook chỉ được giữ một lần.

### Danh sách kiểm tra (in ra)

1. ☐ Mở Payobook tại Thời gian › Máy chấm công
2. ☐ Trên máy: Menu › Comm. › Cài đặt máy chủ đám mây
3. ☐ Loại máy chủ ADMS, Bật tên miền BẬT
4. ☐ Địa chỉ sudima.payobook.com, cổng 443
5. ☐ Proxy TẮT, HTTPS BẬT
6. ☐ Lưu và khởi động lại máy
7. ☐ Máy hiện trong "Máy đang xin kết nối" → Cho phép
8. ☐ Tên, vị trí, múi giờ, ngày bắt đầu ghép → Cho kết nối
9. ☐ Một người chấm công → hiện trong Lượt chấm gần đây
10. ☐ Làm tiếp máy kế tiếp (tổng cộng bảy máy)

---

Screens from the validation workspace (one per state):
`shots/p2-01-empty-with-address.png`, `shots/p2-02-asking-to-connect.png`,
`shots/p2-03-allow-sheet.png`, `shots/p2-04-machine-card.png`,
`shots/p2-05-resend.png`, `shots/p2-06-clock-corrected.png`.
