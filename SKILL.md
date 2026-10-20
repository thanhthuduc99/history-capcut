---
name: history-capcut
description: Làm video lịch sử dạng hoạt hình 2D từ 1 dòng ý tưởng, rồi tự dựng sẵn project trong CapCut desktop (không cần kéo thả). Claude tra và kiểm nguồn, viết kịch bản, làm voice bằng vivibe, gen mỗi câu thoại 1 ảnh bằng Codex image_gen, rồi ghi thẳng draft CapCut gồm ảnh có zoom/punch-in, phụ đề ngắn, voice, nhạc, SFX. Dùng khi user nói "làm video lịch sử", "video hoạt hình lịch sử", "làm clip về <nhân vật / trận đánh>", "bỏ vô capcut", "edit trong capcut", "history capcut".
---

# History → CapCut

User đưa 1 ý tưởng (một nhân vật, một trận đánh, một sự kiện). Claude làm hết, user chỉ việc mở CapCut.

```
ý tưởng → sources.md → vo.txt → voice + mốc từng chữ → mỗi câu 1 ảnh → export/
        → project CapCut dựng sẵn timeline
```

Mọi lệnh chạy từ thư mục gốc repo. Mỗi video là một thư mục `<dir>/<slug>-long/` tự chứa script của nó.

## 0. Cần có

- Windows + CapCut desktop (draft v189 trở lên). Draft nằm ở `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`, đổi bằng biến `CAPCUT_DRAFTS`.
- Python 3.11+ với `pillow numpy faster-whisper`, Node 18+, `ffmpeg`/`ffprobe` trong PATH.
- Codex CLI đăng nhập bằng tài khoản ChatGPT (`codex login`). Ảnh gen qua tool `image_gen` của gói ChatGPT, không cần API key.
- `.env` ở gốc repo: `VIVIBE_API_KEY=...`, `VIVIBE_VOICE=...`. Tuỳ chọn `HC_MUSIC_FILE=<file nhạc>`, `HC_SFX_DIR=<thư mục SFX>` (tên file SFX xem `new_project.py`). Thiếu nhạc hay SFX thì timeline bỏ qua track đó.

## 1. Tạo project

```bash
python .claude/skills/history-capcut/new_project.py <slug> --style <style>
```

`--style` là thời kỳ gần nhất trong `template/style/`: `dong-son` (Hùng Vương, Âu Lạc, Hai Bà Trưng), `938-bach-dang` (thế kỷ 10), `1860s-nam-ky` (Pháp đánh Nam Kỳ), `1954-viet-minh` (chống Pháp). Sau đó sửa `script/style.txt` cho đúng chủ đề: đoạn PERIOD, RECURRING CHARACTERS (mô tả cố định từng nhân vật để ảnh nào cũng giống), NATURE. Giữ nguyên các đoạn về nét, màu, mặt người.

## 2. Nguồn (`sources.md`)

Tra Wikipedia tiếng Việt bằng WebFetch (bài về sự kiện + bài về nhân vật chính). Ghi 2 bảng:
- **Fact dùng được**: mỗi dòng 1 fact + bài nguồn.
- **Chỗ nguồn lệch nhau**: con số hay chi tiết mà các nguồn chép khác nhau, và cách nói trong VO (thường là không nêu, hoặc nói "khoảng", "sử cũ chép").

Truyền thuyết tách riêng. Câu VO nào thuộc truyền thuyết phải mở bằng "Truyền thuyết kể", "Tương truyền" hoặc "Sử cũ chép". Không đưa con số chưa chắc vào VO.

## 3. Kịch bản (`script/vo.txt`)

- **Mỗi dòng đúng 1 câu.** Mỗi câu sẽ có 1 ảnh riêng, nên số dòng = số ảnh. 15-20 câu cho video khoảng 1 phút 15.
- Câu dài 12-25 chữ cho nhịp kể (khoảng 4-5 giây một cảnh). Câu quá ngắn thì 2 giây đã đổi cảnh, xem mệt.
- Chỉ dùng fact trong `sources.md`. Viết năm bằng chữ số (`năm 938`), vivibe tự đọc.
- Không dùng em dash, không cấu trúc "không phải X mà là Y".

## 4. Voice và mốc từng chữ

```bash
cd <dir>/<slug>-long
node script/tts-vivibe.mjs script/vo.txt assets/audio/vo.mp3
python script/words.py          # faster-whisper, ghép với chữ SRT của vivibe -> build/words.json
```

## 5. Cảnh (`script/scenes.json`) và chia shot

Key đặt dạng `"01-cua-song-bach-dang"`, theo đúng thứ tự câu, đủ số câu. Key này cũng là tên file ảnh. Mỗi giá trị là mô tả cảnh bằng tiếng Anh: ai, đang làm gì, ở đâu, góc máy hơi cao, ban ngày hay đêm. Cảnh hiện đại ghi `EXCEPTION: present day`. Cảnh bạo lực: chỉ tả khoảnh khắc trước hoặc sau, không máu, không xác. Chữ trên biển, cờ, sách: "no writing" hoặc "abstract dashes".

```bash
python script/plan.py           # mỗi câu 1 ảnh; câu dài hơn 6,5 giây thì 2 shot cùng ảnh, khác kiểu zoom
```

## 6. Gen ảnh

```bash
python script/gen_img.py <key>          # từng ảnh
python script/quota.py                  # % hạn mức Codex ngăn 5 giờ và ngăn tuần, không tốn hạn mức
```

Lệnh gen dùng model nhẹ (`gpt-5.6-luna`, reasoning `low`, tắt plugin/skill/MCP) và 1-2 ảnh tham chiếu style. Khoảng 15 ảnh tốn 1% ngăn 5 giờ. Chạy cả loạt trong nền.

## 7. Phụ đề và SFX (`script/video.json`)

```json
{"numbers": [["năm chín trăm ba mươi tám", "năm 938"]],
 "cues": [["thủy triều rút", "riser.mp3", -2.0, "riser"], ["thủy triều rút", "impact-bass-2.mp3", 0.3, "hit"]],
 "glue": "ngô quyền|bạch đằng|nam hán"}
```

- `numbers`: cụm số vivibe đọc thành chữ → hiện bằng chữ số, tô vàng.
- `cues`: SFX theo câu thoại. `hit` kèm punch-in vào ảnh, `riser` lấy 2 giây cuối file.
- `glue`: tên riêng, từ ghép không được cắt ngang khi chia phụ đề.

Xem trước phụ đề: `python -c "import sys,json;sys.path.insert(0,'script');import edit_user_draft as E;[print(' '.join(w for w,_ in c['parts'])) for c in E.chunk(E.merge_numbers(json.load(open('build/words.json',encoding='utf-8'))))]"`

## 8. Xuất và dựng CapCut

```bash
python script/export_assets.py                    # export/<slug>-capcut/ + <slug>-phu-de.srt + timeline
python script/create_project.py <tên-project>     # project mới, media pool có sẵn thư mục Anh/Voice/Nhac/SFX
python script/edit_user_draft.py <tên-project> --export
```

`create_project.py` ưu tiên chép một project trống có sẵn trên máy (CapCut tự tạo khi bấm Create project rồi thoát ra) làm khung; không có mới dùng khuôn đóng gói sẵn. Nên mở CapCut tạo 1 project trống trước lần chạy đầu.

**CapCut phải tắt hẳn** lúc chạy 2 lệnh cuối, không thì khi đóng nó ghi đè mất. Có file `.locked` trong thư mục draft nghĩa là đang mở, đừng tắt ngang, báo user đóng. Mỗi lần ghi đều sao lưu draft vào `build/backup/`.

Nếu user tự tạo project và kéo thư mục `export/<slug>-capcut/` vào, chỉ cần chạy lệnh cuối với tên folder draft của project đó. File `.srt` nằm ngoài vì CapCut không nhận srt làm media (nhập bằng Text > Import captions nếu cần).

## Timeline dựng ra

| Track | Nội dung |
|---|---|
| Video | mỗi shot 1 ảnh, zoom vào/ra, lia trái/phải xoay vòng, punch-in ở các cue `hit` |
| Captions | 2-5 chữ một dòng, chạy theo mốc từng chữ, không cắt giữa câu hay từ ghép |
| Voice | 100% |
| Music | 6% (khoảng 18 dB dưới giọng), fade in 1,5s, fade out 3s |
| SFX | whoosh khi đổi cảnh, pop khi hiện số, các cue trong `video.json`, chuẩn về -22 LUFS |

Thông số nhìn (cỡ chữ, vị trí, mức zoom, âm lượng) là hằng số ở đầu `script/edit_user_draft.py`.
