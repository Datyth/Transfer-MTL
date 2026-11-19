# Bản đồ chuyển giao bằng CLIP ViT-L/14

Thí nghiệm thăm dò trên tập phát triển. Bộ kiểm chứng đầy đủ chất lượng mô hình chưa được chạy. Kết quả chưa chứng minh quan hệ hỗ trợ tổng quát và chưa được xác nhận trên tập độc lập.

Màu biểu thị mức thay đổi so với học riêng. Nhãn ghi mức bằng chứng sau đối chứng.

## Mốc học riêng

| Nhóm | Điểm trung bình | Độ lệch chuẩn |
|---|---:|---:|
| So sánh | 49.64% | 1.34% |
| Tồn tại | 53.14% | 0.59% |
| Suy luận logic | 54.79% | 0.34% |
| Thuộc tính | 51.39% | 0.47% |
| Quan hệ | 52.86% | 1.42% |

## Các hướng chuyển giao

| Nguồn | Đích | Cách học | Mức tăng điểm phần trăm | Khoảng tin cậy 95% | Kết luận thăm dò |
|---|---|---|---:|---|---|
| Thuộc tính | Tồn tại | Học lần lượt | -1.14 | [-3.16, +0.83] | chưa đủ bằng chứng |
| Thuộc tính | Tồn tại | Học chung | -2.19 | [-4.66, +0.19] | chưa đủ bằng chứng |
| Quan hệ | Tồn tại | Học lần lượt | -0.22 | [-2.36, +1.98] | chưa đủ bằng chứng |
| Quan hệ | Tồn tại | Học chung | -2.45 | [-5.03, -0.05] | chưa đủ bằng chứng |
| So sánh | Tồn tại | Học lần lượt | -1.44 | [-3.66, +0.85] | chưa đủ bằng chứng |
| So sánh | Tồn tại | Học chung | -1.55 | [-3.86, +0.68] | chưa đủ bằng chứng |
| Suy luận logic | Tồn tại | Học lần lượt | +0.78 | [-1.44, +2.94] | chưa đủ bằng chứng |
| Suy luận logic | Tồn tại | Học chung | -1.04 | [-3.32, +1.10] | chưa đủ bằng chứng |
| Tồn tại | Thuộc tính | Học lần lượt | -0.87 | [-2.79, +1.07] | chưa đủ bằng chứng |
| Tồn tại | Thuộc tính | Học chung | -0.61 | [-2.97, +1.98] | chưa đủ bằng chứng |
| Quan hệ | Thuộc tính | Học lần lượt | -1.24 | [-3.24, +0.64] | chưa đủ bằng chứng |
| Quan hệ | Thuộc tính | Học chung | -0.10 | [-2.27, +2.00] | chưa đủ bằng chứng |
| So sánh | Thuộc tính | Học lần lượt | -0.83 | [-2.54, +1.02] | chưa đủ bằng chứng |
| So sánh | Thuộc tính | Học chung | -1.30 | [-3.17, +0.64] | chưa đủ bằng chứng |
| Suy luận logic | Thuộc tính | Học lần lượt | -1.38 | [-3.37, +0.52] | chưa đủ bằng chứng |
| Suy luận logic | Thuộc tính | Học chung | -1.41 | [-3.76, +1.01] | chưa đủ bằng chứng |
| Tồn tại | Quan hệ | Học lần lượt | -1.85 | [-3.68, +0.02] | chưa đủ bằng chứng |
| Tồn tại | Quan hệ | Học chung | -0.44 | [-2.42, +1.52] | chưa đủ bằng chứng |
| Thuộc tính | Quan hệ | Học lần lượt | +0.24 | [-2.53, +2.80] | chưa đủ bằng chứng |
| Thuộc tính | Quan hệ | Học chung | +0.05 | [-1.96, +2.18] | chưa đủ bằng chứng |
| So sánh | Quan hệ | Học lần lượt | -0.24 | [-2.97, +2.34] | chưa đủ bằng chứng |
| So sánh | Quan hệ | Học chung | -0.62 | [-2.51, +1.45] | chưa đủ bằng chứng |
| Suy luận logic | Quan hệ | Học lần lượt | -0.47 | [-2.61, +1.61] | chưa đủ bằng chứng |
| Suy luận logic | Quan hệ | Học chung | -2.17 | [-4.11, -0.22] | chưa đủ bằng chứng |
| Tồn tại | So sánh | Học lần lượt | +1.29 | [-1.12, +3.70] | chưa đủ bằng chứng |
| Tồn tại | So sánh | Học chung | +1.13 | [-1.59, +3.98] | chưa đủ bằng chứng |
| Thuộc tính | So sánh | Học lần lượt | +1.72 | [-0.66, +4.18] | chưa đủ bằng chứng |
| Thuộc tính | So sánh | Học chung | +0.49 | [-2.06, +3.24] | chưa đủ bằng chứng |
| Quan hệ | So sánh | Học lần lượt | +1.04 | [-1.89, +3.83] | chưa đủ bằng chứng |
| Quan hệ | So sánh | Học chung | +1.52 | [-1.70, +4.71] | chưa đủ bằng chứng |
| Suy luận logic | So sánh | Học lần lượt | +0.18 | [-2.23, +2.49] | chưa đủ bằng chứng |
| Suy luận logic | So sánh | Học chung | +0.16 | [-2.36, +2.84] | chưa đủ bằng chứng |
| Tồn tại | Suy luận logic | Học lần lượt | +0.40 | [-1.22, +1.84] | chưa đủ bằng chứng |
| Tồn tại | Suy luận logic | Học chung | -0.85 | [-1.85, +0.13] | chưa đủ bằng chứng |
| Thuộc tính | Suy luận logic | Học lần lượt | -1.35 | [-2.29, -0.45] | chưa đủ bằng chứng |
| Thuộc tính | Suy luận logic | Học chung | -1.73 | [-3.11, -0.41] | chưa đủ bằng chứng |
| Quan hệ | Suy luận logic | Học lần lượt | -0.69 | [-1.89, +0.59] | chưa đủ bằng chứng |
| Quan hệ | Suy luận logic | Học chung | -1.94 | [-3.02, -0.83] | chưa đủ bằng chứng |
| So sánh | Suy luận logic | Học lần lượt | -1.73 | [-2.74, -0.70] | chưa đủ bằng chứng |
| So sánh | Suy luận logic | Học chung | -1.51 | [-2.82, -0.29] | chưa đủ bằng chứng |

Độ chính xác cân bằng được dùng cho nhóm quan hệ, độ chính xác thông thường cho các nhóm khác.
Mốc cải thiện tối thiểu được đặt trước ở một điểm phần trăm. Ba lần khởi tạo phải cùng chiều để đạt quy tắc 80%.
Không có bản sao ma trận dùng ảnh trắng hoặc nguồn tách ảnh. Không diễn giải kết quả này thành bằng chứng chắc chắn về chuyển giao thị giác.

## Năm nhóm nhiệm vụ

Số kết quả có bằng chứng: 0.
