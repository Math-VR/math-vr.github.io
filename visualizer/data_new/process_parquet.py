import os
import sys
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List
from PIL import Image
import io


def ensure_dir(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def read_parquet_table(parquet_path: str):
    try:
        import pyarrow.parquet as pq
    except Exception as e:
        raise RuntimeError("需要安装 pyarrow 才能读取 parquet: pip install pyarrow") from e

    try:
        # 使用 ParquetFile 以更清晰的错误信息
        pf = pq.ParquetFile(parquet_path)
        table = pf.read()
        return table
    except Exception as e:
        # 常见：footer 缺失或损坏
        raise RuntimeError(
            f"无法读取 parquet 文件: {parquet_path}. 可能尾部 footer 缺失或文件损坏。原始错误: {e}"
        ) from e


def map_row_to_public_format(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    将一行数据映射为 data_public.js 中的对象结构。
    期望字段（若 parquet 字段名不同请在此处做映射）：
      - id -> pid
      - question -> question
      - image -> image 相对路径，比如 images/xxx.jpg
      - options -> choices（允许为空/None）
      - answer -> answer（字符串化）
      - subject -> metadata.category
      - level -> metadata.grade (前缀 'level ' 或保持一致)
    """

    pid = str(row.get("id", ""))
    question = row.get("question", "")
    image = row.get("image", "")
    options = row.get("options")
    answer = row.get("answer", "")
    # 兼容新的列名：category
    subject = row.get("subject") if row.get("subject") is not None else row.get("category", "")
    level = row.get("level")

    # 归一化
    if answer is None:
        answer = ""
    if not isinstance(answer, str):
        answer = str(answer)

    if options is None:
        choices = []
    else:
        choices = list(options)

    # 推断题型
    question_type = "multi_choice" if choices else "free_form"

    # 生成 metadata.grade，与 data_public.js 一致（小写 level N）
    if isinstance(level, (int, float)):
        grade = f"level {int(level)}"
    elif isinstance(level, str):
        grade = level if level.lower().startswith("level") else f"level {level}"
    else:
        grade = "level 0"

    # 结果对象
    return {
        "question": question,
        "image": image,
        "choices": choices,
        "answer": answer,
        "question_type": question_type,
        "pid": pid,
        "metadata": {
            # 这里默认全部归到 test，可根据需要改为 testmini 之类
            "split": "test",
            "category": subject,
            "grade": grade,
        },
    }


def guess_image_ext(data: bytes) -> str:
    if not data:
        return ".bin"
    # PNG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    # JPEG
    if data.startswith(b"\xff\xd8"):
        return ".jpg"
    # GIF
    if data.startswith(b"GIF8"):
        return ".gif"
    # WebP (RIFF...WEBP)
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return ".webp"
    return ".bin"


def extract_images_from_text(text: str) -> List[int]:
    """从文本中提取 <imageN> 占位符的数字"""
    indices = []
    for m in re.finditer(r"<image(\d+)>", text):
        try:
            indices.append(int(m.group(1)))
        except Exception:
            continue
    return indices


def save_as_jpg(data: bytes, output_path: str) -> bool:
    """将图片数据保存为 JPG 格式"""
    try:
        img = Image.open(io.BytesIO(data))
        # 如果是 RGBA，转换为 RGB
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        img.save(output_path, 'JPEG', quality=95)
        return True
    except Exception as e:
        print(f"保存JPG失败 {output_path}: {e}")
        return False


def process_text_with_images(text: str, image_paths: List[str]) -> str:
    """处理文本中的图片占位符，替换为图片路径信息"""
    if not text or not image_paths:
        return text
    
    # 找到所有 <imageN> 占位符并按顺序替换
    image_counter = 1
    def replace_image_placeholder(match):
        nonlocal image_counter
        try:
            if image_counter <= len(image_paths):
                img_tag = f"<img src='{image_paths[image_counter - 1]}' class='question-img' />"
                image_counter += 1
                return img_tag
            else:
                return match.group(0)  # 保持原样
        except (ValueError, IndexError):
            return match.group(0)  # 保持原样
    
    # 替换 <imageN> 为实际的图片标签
    processed_text = re.sub(r'<image\d+>', replace_image_placeholder, text)
    return processed_text


def main():
    # 工作目录：仓库根目录
    visualizer_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_root = os.path.dirname(visualizer_dir)
    parquet_path = os.path.join(visualizer_dir, "test-00000-of-00001.parquet")
    out_dir = os.path.join(visualizer_dir, "data_new")
    ensure_dir(out_dir)
    out_img_dir = os.path.join(out_dir, "images")
    ensure_dir(out_img_dir)

    try:
        table = read_parquet_table(parquet_path)
    except RuntimeError as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(2)

    # 将表转为 Python 字典列表
    pydict = table.to_pydict()
    num_rows = len(next(iter(pydict.values()))) if pydict else 0

    # 构造与 data_public.js 相同的字典：key 为 pid（即 id 字符串），value 为对象
    output: Dict[str, Dict[str, Any]] = {}
    # 找到所有可能的图片列：
    # - 旧格式：image, image1, image2 ...（字符串路径）
    # - 你的 parquet：image1..imageK 为 struct(bytes,path)
    # - 也兼容 <imageN> 这类命名
    all_columns = list(pydict.keys())
    image_cols = []
    for c in all_columns:
        if re.fullmatch(r"image(\d+)?", c):
            image_cols.append(c)
        elif re.fullmatch(r"<image\d+>", c):
            image_cols.append(c)

    # 排序：无数字的 image 最前；数字按升序；保持尖括号与非尖括号共同排序
    def _img_key(name: str):
        if name == "image":
            return (0, 0)
        m1 = re.fullmatch(r"image(\d+)", name)
        if m1:
            return (1, int(m1.group(1)))
        m2 = re.fullmatch(r"<image(\d+)>", name)
        if m2:
            return (2, int(m2.group(1)))
        return (9, 999999)

    image_cols.sort(key=_img_key)

    output: Dict[str, Dict[str, Any]] = {}
    for idx in range(num_rows):
        row = {k: v[idx] for k, v in pydict.items()}
        try:
            obj = map_row_to_public_format(row)
            pid = obj["pid"] or str(idx)

            # 从 question 内提取占位出现顺序，只导出在题干中出现的 imageN
            qtext = obj.get("question") or ""
            order_indices: List[int] = []
            for m in re.finditer(r"<image(\d+)>", qtext):
                try:
                    order_indices.append(int(m.group(1)))
                except Exception:
                    continue

            # 从 analysis 内提取占位出现顺序，只导出在分析中出现的 imageN
            analysis_text = row.get("analysis") or ""
            analysis_indices = extract_images_from_text(analysis_text)

            # 对应提取 struct 或路径
            saved_paths: List[str] = []
            analysis_saved_paths: List[str] = []
            seq = 1
            seen = set()
            for i in order_indices:
                if i in seen:
                    continue
                seen.add(i)
                key_candidates = [f"image{i}", f"<image{i}>"]
                val = None
                for k in key_candidates:
                    if k in row:
                        val = row[k]
                        break
                if val is None:
                    continue
                # val 可能是字符串路径或 struct(dict)
                if isinstance(val, str):
                    # 路径：复制
                    basename = os.path.basename(val)
                    ext = os.path.splitext(basename)[1] or ".jpg"
                    new_name = f"{pid}_{seq}{ext}"
                    seq += 1
                    candidates = [
                        os.path.join(visualizer_dir, val),
                        os.path.join(visualizer_dir, "data", val),
                        os.path.join(os.path.dirname(visualizer_dir), val),
                    ]
                    src_path = next((c for c in candidates if os.path.isfile(c)), None)
                    if src_path:
                        dst_path = os.path.join(out_img_dir, new_name)
                        if not os.path.isfile(dst_path):
                            shutil.copyfile(src_path, dst_path)
                        saved_paths.append(f"data_new/images/{new_name}")
                elif isinstance(val, dict):
                    data = val.get("bytes")
                    if isinstance(data, (bytes, bytearray)) and data:
                        new_name = f"{pid}_{seq}.jpg"
                        seq += 1
                        dst_path = os.path.join(out_img_dir, new_name)
                        try:
                            if not os.path.isfile(dst_path):
                                save_as_jpg(data, dst_path)
                            saved_paths.append(f"data_new/images/{new_name}")
                        except Exception as werr:
                            sys.stderr.write(f"写入图片失败 {dst_path}: {werr}\n")

            # 处理 analysis 中的图片
            analysis_seq = 1
            analysis_seen = set()
            for i in analysis_indices:
                if i in analysis_seen:
                    continue
                analysis_seen.add(i)
                key_candidates = [f"image{i}", f"<image{i}>"]
                val = None
                for k in key_candidates:
                    if k in row:
                        val = row[k]
                        break
                if val is None:
                    continue
                # val 可能是字符串路径或 struct(dict)
                if isinstance(val, str):
                    # 路径：复制
                    basename = os.path.basename(val)
                    ext = os.path.splitext(basename)[1] or ".jpg"
                    new_name = f"{pid}_analysis_{analysis_seq}{ext}"
                    analysis_seq += 1
                    candidates = [
                        os.path.join(visualizer_dir, val),
                        os.path.join(visualizer_dir, "data", val),
                        os.path.join(os.path.dirname(visualizer_dir), val),
                    ]
                    src_path = next((c for c in candidates if os.path.isfile(c)), None)
                    if src_path:
                        dst_path = os.path.join(out_img_dir, new_name)
                        if not os.path.isfile(dst_path):
                            shutil.copyfile(src_path, dst_path)
                        analysis_saved_paths.append(f"data_new/images/{new_name}")
                elif isinstance(val, dict):
                    data = val.get("bytes")
                    if isinstance(data, (bytes, bytearray)) and data:
                        new_name = f"{pid}_analysis_{analysis_seq}.jpg"
                        analysis_seq += 1
                        dst_path = os.path.join(out_img_dir, new_name)
                        try:
                            if not os.path.isfile(dst_path):
                                save_as_jpg(data, dst_path)
                            analysis_saved_paths.append(f"data_new/images/{new_name}")
                        except Exception as werr:
                            sys.stderr.write(f"写入analysis图片失败 {dst_path}: {werr}\n")

            # 处理 question 中的图片位置
            question_with_images = process_text_with_images(obj.get("question"), saved_paths)
            
            # 处理 analysis 中的图片位置
            analysis_with_images = process_text_with_images(analysis_text, analysis_saved_paths)
            
            # 仅保留所需字段
            minimal = {
                "question": question_with_images,
                "image": saved_paths,  # 按题干占位顺序的图片相对路径列表
                "category": obj.get("metadata", {}).get("category"),
                "analysis": analysis_with_images,
                "analysis_image": analysis_saved_paths,  # 按分析占位顺序的图片相对路径列表
            }
            output[pid] = minimal
        except Exception as e:
            # 跳过异常行但不中断整体流程
            sys.stderr.write(f"行 {idx} 转换失败: {e}\n")
            continue

    # 输出文件：data_public.js 同格式，但放在 data_new/data_public.js
    out_file = os.path.join(out_dir, "data_public.js")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("test_data = ")
        json.dump(output, f, indent=4, ensure_ascii=False)

    print(f"已写出 {len(output)} 条到 {out_file}")


if __name__ == "__main__":
    main()


