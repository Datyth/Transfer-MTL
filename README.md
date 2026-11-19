# Học nhiều nhiệm vụ trả lời câu hỏi bằng hình ảnh

Đọc [tổng quan dự án và báo cáo thực nghiệm](PROJECT_OVERVIEW_EXPERIMENT_REPORT.md) để xem nền tảng học nhiều nhiệm vụ, dữ liệu, quy trình, hành trình thực nghiệm và phân tích kết quả kèm tám hình minh họa.

Kho lưu mã nguồn, cấu hình, báo cáo và bảng/hình tổng hợp. Dữ liệu GQA, trọng số mô hình, cache và kết quả chi tiết của từng lượt chạy được giữ cục bộ theo `.gitignore`; chúng cần được chuẩn bị lại nếu muốn chạy thực nghiệm trên máy khác.

Dự án nghiên cứu câu hỏi: **học một loại câu hỏi trước có giúp mô hình trả lời tốt hơn một loại câu hỏi khác không?** Dữ liệu GQA gồm ảnh, câu hỏi và chương trình mô tả các bước suy luận. Chương trình chỉ dùng để phân nhóm và phân tích, không được đưa vào mô hình.

Ví dụ, học cách xác định có một vật trong ảnh có giúp trả lời câu hỏi kết hợp hai điều kiện không? Ta so sánh với mô hình chỉ học câu hỏi đích và kiểm tra lợi ích có đến từ việc nhìn thêm dữ liệu hoặc học mẹo trong câu hỏi.

## Đợt thực nghiệm thu gọn để báo cáo

Đợt hiện tại chỉ đo năm nhóm, đủ 20 hướng, với 1.000 câu đích, ba lần khởi tạo và cả học lần lượt lẫn học chung. Có 39 lượt học nguồn và 225 lượt học đích, trong đó gồm 15 mốc học riêng. Ba đối chứng dữ liệu gồm nguồn cùng nhiệm vụ, nguồn ngoài nhóm và nguồn đảo nhãn.

Theo yêu cầu thu gọn, đợt này bỏ 14 họ, đường học, bộ kiểm chứng đầy đủ chất lượng mô hình và các bản sao ma trận dùng ảnh trắng hoặc nguồn tách ảnh. Các kiểm thử kỹ thuật vẫn bắt buộc. Kết quả được đánh giá trên tập phát triển và ghi rõ là **thăm dò**, chưa phải xác nhận độc lập hay bằng chứng chắc chắn về cơ chế chuyển giao thị giác.

Độ chính xác là thước đo chính, riêng nhóm quan hệ dùng độ chính xác cân bằng. Mức cải thiện tối thiểu được đặt trước ở một điểm phần trăm. Tổn thất xác suất, khả năng xếp hạng đáp án, khoảng tin cậy và các đối chứng được báo kèm. Tập xác nhận và tập kiểm tra cuối không được đánh giá trong đợt này.

## Các nhóm nhiệm vụ

| Nhóm | Năng lực muốn đo | Ví dụ minh họa |
|---|---|---|
| Tồn tại | Xác định có vật thỏa điều kiện | Có chiếc xe màu đỏ không? |
| Thuộc tính | Kiểm tra đặc điểm của vật | Chiếc áo có màu xanh không? |
| Quan hệ | Kiểm tra quan hệ giữa các vật | Cốc có ở bên trái đĩa không? |
| So sánh | So sánh thuộc tính của các vật | Hai chiếc áo có cùng màu không? |
| Suy luận logic | Kết hợp các điều kiện | Có cả chó và mèo không? |

Các ví dụ tiếng Việt dùng để giải thích. Câu hỏi thực nghiệm giữ nguyên dữ liệu gốc. Quy tắc phân nhóm và danh sách câu hỏi được khóa từ giai đoạn kiểm toán.

Ngoài năm nhóm, nghiên cứu đo **14 họ câu hỏi** có ít nhất 2.500 mẫu huấn luyện. Mỗi họ là một kiểu câu hỏi cụ thể trong nhóm. Bước kiểm tra đầu vào xuất danh sách, ví dụ và số lượng từng họ.

## Thiết kế ma trận chuyển giao đầy đủ

Phần này mô tả thiết kế dài hạn. Thiết kế đầy đủ đã dừng ở dự toán khoảng 129 giờ GPU, vượt giới hạn 24 giờ. Đợt thu gọn ở trên được chạy riêng và giữ nguyên kết quả đã có.

Bản đồ có hướng. Tồn tại → suy luận logic và suy luận logic → tồn tại là hai phép đo khác nhau.

| Cấp đo | Số hướng | Câu nguồn | Câu đích | Số lần khởi tạo |
|---|---:|---:|---|---:|
| Năm nhóm | 20 | 10.000 | 250, 1.000, 4.000 | 5 |
| Mười bốn họ | 182 | 2.000 | 500 | 3 |

- **Học riêng** chỉ dùng dữ liệu đích và là mốc so sánh.
- **Học lần lượt** học nguồn 10 lượt, sau đó học đích 10 lượt với bộ tối ưu mới.
- **Học chung** học từ đầu trên nguồn và đích trộn chung trong 10 lượt.

Các nhánh so sánh dùng cùng mẫu đích và cùng lần khởi tạo. Ở cấp nhóm, 250 câu nằm trong 1.000 câu, còn 1.000 câu nằm trong 4.000 câu.

Mức cải thiện bằng điểm sau khi dùng nguồn trừ điểm học riêng. Từ 55% lên 58% là tăng **3 điểm phần trăm**. Với tổn thất xác suất, lấy tổn thất học riêng trừ tổn thất sau khi dùng nguồn để số dương luôn biểu thị cải thiện.

### Đối chứng và cách đọc

- Thêm dữ liệu cùng nhiệm vụ, tách khỏi mẫu đích.
- Dùng câu hỏi ngoài nhóm để kiểm tra lợi ích từ định dạng trả lời hoặc phân bố đáp án. Cấp nhóm dùng 5.371 câu, cấp họ lấy 2.000 câu.
- Đảo nhãn một nguồn được chỉ định trước cho từng đích, giữ nguyên câu hỏi và ảnh.
- Ở cấp nhóm, thay ảnh bằng ảnh trắng và lấy nguồn có ảnh tách khỏi mẫu đích tại mức 1.000 câu.
- Đánh giá riêng trên câu khó đối với mô hình chỉ đọc câu hỏi và các nhóm suy luận đã đăng ký.

Mỗi hướng được ghi **hỗ trợ**, **gây hại** hoặc **chưa đủ bằng chứng**. Một hướng hỗ trợ cần vượt mức cải thiện tối thiểu, có khoảng tin cậy phù hợp, cùng chiều ở ít nhất 80% lần khởi tạo, vượt đối chứng và còn bằng chứng trên câu hỏi khó. Nguồn cùng nhiệm vụ là mốc tham khảo, không bắt buộc phải vượt qua.

Khoảng tin cậy lấy mẫu lại theo lần khởi tạo và ảnh. Kiểm định được điều chỉnh vì có nhiều hướng được đo. Khả năng xếp hạng đáp án được báo bổ sung bằng mức thay đổi trung bình. Mỗi cách học có bản đồ riêng.

## Những thực nghiệm đã chạy

Các giai đoạn đầu đã kiểm toán dữ liệu, chia tập theo ảnh, xây quy tắc phân nhóm và đo mô hình chỉ đọc câu hỏi. Tiếp đó, Qwen2.5-VL-3B được đánh giá khi chưa huấn luyện thêm. Xem [hướng dẫn kiểm toán](gqa_audit/README.md) và [kết quả giai đoạn 3](gqa_audit/outputs/stage3/metrics_3b.csv).

### Thăm dò bằng CLIP bản cơ sở

Giai đoạn 3.5 đã chạy 120 cấu hình chọn cách huấn luyện, 85 lượt đo đường học, 25 lượt dùng ảnh trắng, 27 lượt học nguồn và 99 lượt học đích.

Mô hình dùng CLIP ViT-B/16 đóng băng, bộ kết hợp bốn tầng và một đầu trả lời có hoặc không. Cách huấn luyện được chọn có tốc độ học 0,0001, đóng băng bộ mã hóa câu hỏi và học 10 lượt.

| Nhóm | Ảnh thật, toàn bộ mẫu huấn luyện | Ảnh trắng |
|---|---:|---:|
| Tồn tại | 61,57% | 56,19% |
| Thuộc tính | 53,11% | 53,99% |
| Quan hệ | 65,74% | 67,12% |
| So sánh | 50,70% | 53,49% |
| Suy luận logic | 76,11% | 69,87% |

Quan hệ dùng độ chính xác cân bằng trên phần câu hỏi quan hệ đã chỉ định. Các nhóm khác dùng độ chính xác thông thường. Bảng là trung bình hai lần khởi tạo trên tập phát triển.

Cả năm nhóm chưa đạt ngưỡng vượt mốc chỉ đọc câu hỏi 10 điểm phần trăm và ngưỡng lợi ích ảnh 10 điểm phần trăm. Các nguồn khác nhiệm vụ đã thử chưa cho thấy lợi ích rõ. Thêm dữ liệu cùng nhiệm vụ giúp suy luận logic và quan hệ, còn so sánh vẫn gần mức ngẫu nhiên. Đây là giới hạn của mô hình thăm dò, chưa đủ để kết luận các nhiệm vụ không thể hỗ trợ nhau.

### Thăm dò huấn luyện bổ sung bằng Qwen

Bốn lượt đã hoàn thành trên nhóm so sánh, mỗi lượt đánh giá 1.705 câu phát triển. Điểm trung bình đạt 75,37% với 1.000 câu huấn luyện và 76,83% với 4.000 câu, so với mốc 72,14% khi chưa huấn luyện thêm. Kiểm tra bộ đánh giá trên 128 câu có sai khác điểm số bằng không.

Qwen học được nhóm so sánh dù mô hình thăm dò còn yếu. Phép thử này chưa đo chuyển giao giữa nhiệm vụ. **Đợt chạy mới chỉ dùng CLIP, kiểm chứng bằng Qwen để sau.** [Các lượt chạy đã có](gqa_audit/outputs/stage3_5/qwen_runs) được giữ làm bằng chứng thăm dò.

## Đợt chạy CLIP bản lớn

CLIP ViT-L/14 dùng ảnh ở độ phân giải 224. Ảnh được thêm viền để giữ toàn bộ nội dung rồi lấy 257 vị trí đặc trưng ở lớp áp chót. Bộ kết hợp có bốn tầng, chiều 512. Bộ mã hóa ảnh và câu hỏi được đóng băng.

Ở thiết kế đầy đủ, hàng đợi kiểm tra khả năng dùng ảnh, đường học, độ dao động và chi phí trước ma trận. Đợt thu gọn bỏ bộ kiểm chứng chất lượng theo yêu cầu, nhưng vẫn giữ kiểm thử kỹ thuật và giới hạn thời gian. Bộ đếm 24 giờ tính cả thời gian tạo đặc trưng đã dùng. Nếu dự toán vượt giới hạn, chương trình dừng và ghi rõ phần chưa hoàn thành.

Thiết kế chính cần được khóa trước khi đánh giá trên tập xác nhận. Đợt thu gọn chỉ đánh giá trên tập phát triển. Tập kiểm tra cuối vẫn được niêm phong.

<!-- KET_QUA_TU_DONG -->

Đã hoàn thành đợt thí nghiệm thăm dò giữa năm nhóm trên tập phát triển. Bộ kiểm chứng đầy đủ chất lượng mô hình được bỏ qua theo yêu cầu, kết quả chưa phải xác nhận độc lập.

- [Trạng thái hàng đợi](gqa_audit/outputs/bao_cao_chuyen_giao_clip_l14/status.json)
- [Dự toán chi phí](gqa_audit/outputs/bao_cao_chuyen_giao_clip_l14/projection.json)
- [Bảng các hướng đã đo](gqa_audit/outputs/bao_cao_chuyen_giao_clip_l14/edges.csv)
- [Báo cáo bản đồ](gqa_audit/outputs/bao_cao_chuyen_giao_clip_l14/BAO_CAO.md)
<!-- HET_KET_QUA_TU_DONG -->

## Chuẩn bị và chạy

Môi trường dùng Python 3.11, PyTorch 2.9.1 với CUDA 12.8 và Transformers 4.57.1. Dữ liệu và trọng số lớn nằm trong máy, không nằm trong kho mã. Cần GQA cùng kết quả kiểm toán đã có. Lệnh chuẩn bị tải đúng phiên bản CLIP bản lớn đã khóa.

```bash
cd vqa-mtl
conda activate datpt_mtl
python scripts/run_chuyen_giao.py kiem-tra --bao-cao
python scripts/run_chuyen_giao.py chuan-bi --bao-cao
python -m pytest -q
python scripts/queue_chuyen_giao.py --bao-cao
```

Lệnh cuối tạo hàng đợi nền. Có thể đóng cửa sổ dòng lệnh. Hàng đợi chờ GPU rảnh và không tạo lượt thứ hai khi đã có một lượt hoạt động. Nó ghi nhật ký và trạng thái, không cần theo dõi thủ công.

Xem trạng thái khi cần:

```bash
python scripts/run_chuyen_giao.py trang-thai --bao-cao
```

Sau gián đoạn, dùng lại lệnh xếp hàng để tiếp tục. Chỉ kết quả có cấu hình, dữ liệu và dấu kiểm tra khớp mới được dùng lại. Lượt dở được chạy lại từ đầu. Máy khởi động lại cần gọi lại lệnh xếp hàng.

## Vị trí mã và kết quả

- `src/vqa_research/chuyen_giao/` chứa mã CLIP bản lớn.
- `gqa_audit/outputs/chuyen_giao_clip_l14/` chứa trạng thái, nhật ký, danh sách lượt chạy, dự toán, bảng điểm và bản đồ.
- `gqa_audit/outputs/bao_cao_chuyen_giao_clip_l14/` chứa kết quả riêng của đợt thu gọn để báo cáo.
- `data/features/clip_vitl14_224/` chứa đặc trưng ảnh riêng cho bản lớn.
- `checkpoints/` chứa trọng số cục bộ.
- `tests/` chứa phép kiểm tra dữ liệu, mô hình và thống kê.

Chỉ xem bản đồ là hoàn chỉnh khi mọi lượt bắt buộc đã qua kiểm tra và hàng đợi báo hoàn tất. Nếu chưa đủ bằng chứng, dự án giữ nguyên kết luận đó thay vì chọn riêng các con số thuận lợi.
