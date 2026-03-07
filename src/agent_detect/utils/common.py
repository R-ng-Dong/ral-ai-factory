import cv2
import torch
import numpy as np
from ultralytics.engine.results import Results
from ultralytics.utils.plotting import Annotator, colors
from copy import deepcopy


def to_rgb(image: np.ndarray):
    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR) if image.ndim == 2 else image


def plot(
    results: Results,
    pil: bool = False,
    probs: bool = False,
    show_conf: bool = True,
    show_box: bool = True,
    show_label: bool = True,
    label_pos: tuple = (0, 0),
    color_mode: str = "class",
    line_width: int | None = None,
    font_size: int | None = None,
    font: str = "Arial.ttf",
) -> np.ndarray:
    """Plot detection results on the image.

    Args:
        results (Results): YOLO detection results
        pil (bool): Whether to use PIL for drawing
        probs (bool): Whether to show probabilities
        color_mode (str): Color mode - 'instance' or 'class'
        line_width (int): Width of bounding box lines
        font_size (int): Size of label font
        font (str): Font to use for labels

    Returns:
        np.ndarray: Annotated image
    """
    if color_mode not in {"instance", "class"}:
        raise ValueError(f"Invalid color_mode: {color_mode}")

    # Initialize annotator
    annotator = Annotator(
        deepcopy(results.orig_img),
        line_width,
        font_size,
        font,
        pil or (results.probs is not None and probs),
        example=results.names[1],
    )

    # Plot detection boxes
    if results.boxes is not None and show_box:
        for i, box in enumerate(reversed(results.boxes)):
            cls_id = int(box.cls)
            conf = float(box.conf) if show_conf else None
            track_id = (
                int(box.id.item())
                if (box.is_track and hasattr(box, "id") and box.id is not None)
                else None
            )

            # Generate label text
            name = (
                f"id:{track_id} {results.names[cls_id]}"
                if track_id
                else results.names[cls_id]
            )
            label = (
                f"{name} {conf:.2f}"
                if conf and show_label
                else name
                if show_label
                else f"{conf:.2f}"
                if conf
                else None
            )

            # Determine color index
            color_idx = cls_id if color_mode == "class" else track_id if track_id else i
            if color_idx is None:
                continue

            # Draw box and label
            _box_label(
                annotator,
                box.xyxy.squeeze(),
                label,
                label_pos,
                color=colors(color_idx, True),
            )

    return annotator.result()


def _box_label(
    annotator: Annotator,
    box,
    label: str | None = "",
    label_pos: tuple = (0, 0),
    color: tuple = (128, 128, 128),
    txt_color: tuple = (255, 255, 255),
):
    """Draw a bounding box with label on the image."""
    if not annotator:
        return

    box = box.tolist() if isinstance(box, torch.Tensor) else box
    txt_color = annotator.get_txt_color(color, txt_color)

    # Adjust base position according to label_pos
    p1 = (int(box[0]) + label_pos[0], int(box[1]) + label_pos[1])

    if annotator.pil:
        annotator.draw.rectangle(box, width=annotator.lw, outline=color)
        if label:
            bbox = annotator.font.getbbox(label)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            outside = p1[1] >= h
            p1 = (min(p1[0], getattr(annotator.im, "width") - w), p1[1])

            annotator.draw.rectangle(
                (
                    p1[0],
                    p1[1] - h if outside else p1[1],
                    p1[0] + w + 1,
                    p1[1] + 1 if outside else p1[1] + h + 1,
                ),
                fill=color,
            )
            annotator.draw.text(
                (p1[0], p1[1] - h if outside else p1[1]),
                label,
                fill=txt_color,
                font=annotator.font,
            )
    else:
        cv2.rectangle(
            np.asarray(annotator.im),
            (int(box[0]), int(box[1])),
            (int(box[2]), int(box[3])),
            color,
            thickness=annotator.lw,
            lineType=cv2.LINE_AA,
        )
        if label:
            w, h = cv2.getTextSize(
                label, 0, fontScale=annotator.sf, thickness=annotator.tf
            )[0]
            h += 3
            outside = p1[1] >= h
            im_array = np.asarray(annotator.im)
            p1 = (min(p1[0], im_array.shape[1] - w), p1[1])
            p2 = p1[0] + w, p1[1] - h if outside else p1[1] + h

            cv2.rectangle(im_array, p1, p2, color, -1, cv2.LINE_AA)
            cv2.putText(
                im_array,
                label,
                (p1[0], p1[1] - 2 if outside else p1[1] + h - 1),
                0,
                annotator.sf,
                txt_color,
                thickness=annotator.tf,
                lineType=cv2.LINE_AA,
            )
            annotator.im = im_array


def put_status(frame: np.ndarray, status: str, font_scale: float = 1.0) -> np.ndarray:
    """
    frame: np.ndarray (BGR)
    status: string cần hiển thị
    """
    # chọn vị trí (tọa độ pixel ảnh)
    pos = (10, 40)  # (x, y)

    # font, kích thước, màu, độ dày
    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 2

    # Chọn màu theo status
    st = status.lower()
    if st == "ok":
        color = (0, 255, 0)  # xanh lá
    elif st == "ng":
        color = (0, 0, 255)  # đỏ
    elif st == "err":
        color = (0, 255, 255)  # vàng
    else:
        color = (255, 255, 255)  # trắng (hoặc bạn đổi sang tím, xanh dương...)

    # thêm chữ lên frame
    cv2.putText(
        frame,
        f"Status: {status}",
        pos,
        font,
        font_scale,
        color,
        thickness,
        cv2.LINE_AA,
    )

    # phát frame ra ngoài
    return frame


def draw_info_box(frame: np.ndarray, meta: dict[str, any]) -> np.ndarray:
    """
    Vẽ khung thông tin overlay lên frame.
    meta: {
        'vít': {required, detected},
        'lỗ vít': {required, detected},
        'accuracy': float (0..100)
    }
    """
    if not meta:
        return frame

    h, w = frame.shape[:2]
    # Kích thước box
    bw, bh = 220, 120
    px, py = 10, 60  # Vị trí (sau status)

    # Vẽ nền bán trong suốt
    overlay = frame.copy()
    cv2.rectangle(overlay, (px, py), (px + bw, py + bh), (40, 40, 40), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # Vẽ viền
    cv2.rectangle(frame, (px, py), (px + bw, py + bh), (200, 200, 200), 1)

    # Nội dung
    font = cv2.FONT_HERSHEY_SIMPLEX
    fs = 0.55
    color = (255, 255, 255)
    thick = 1

    # Dòng 1: Vít
    screw = meta.get("vít", {"required": 0, "detected": 0})
    s_text = f"Vit: {screw['detected']}/{screw['required']}"
    cv2.putText(frame, s_text, (px + 10, py + 30), font, fs, color, thick, cv2.LINE_AA)

    # Dòng 2: Lỗ vít
    hole = meta.get("lỗ vít", {"required": 0, "detected": 0})
    h_text = f"Lo vit: {hole['detected']}/{hole['required']}"
    cv2.putText(frame, h_text, (px + 10, py + 60), font, fs, color, thick, cv2.LINE_AA)

    # Dòng 3: Độ chính xác
    acc = meta.get("accuracy", 0.0)
    a_text = f"Accuracy: {acc:.1f}%"
    # Đổi màu theo độ chính xác
    a_color = (0, 255, 0) if acc > 80 else (0, 255, 255) if acc > 50 else (0, 0, 255)
    cv2.putText(frame, a_text, (px + 10, py + 95), font, 0.6, a_color, 2, cv2.LINE_AA)

    return frame
