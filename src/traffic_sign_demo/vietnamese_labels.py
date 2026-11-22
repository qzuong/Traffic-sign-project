"""Vietnamese presentation labels for the CNN's existing class indices."""

VIETNAMESE_CLASSES = {
    0: "Tốc độ tối đa (20km/h)",
    1: "Tốc độ tối đa (30km/h)",
    2: "Tốc độ tối đa (50km/h)",
    3: "Tốc độ tối đa (60km/h)",
    4: "Tốc độ tối đa (70km/h)",
    5: "Tốc độ tối đa (80km/h)",
    6: "Hết hạn chế tốc độ (80km/h)",
    7: "Tốc độ tối đa (100km/h)",
    8: "Tốc độ tối đa (120km/h)",
    9: "Cấm vượt",
    10: "Cấm xe tải vượt",
    11: "Giao nhau với đường ưu tiên",
    12: "Đường ưu tiên",
    13: "Nhường đường",
    14: "Dừng lại (Stop)",
    15: "Đường cấm",
    16: "Cấm xe tải (trên 3.5 tấn)",
    17: "Cấm đi ngược chiều",
    18: "Nguy hiểm khác",
    19: "Chỗ ngoặt nguy hiểm (trái)",
    20: "Chỗ ngoặt nguy hiểm (phải)",
    21: "Đường cong liên tục",
    22: "Đường gồ ghề",
    23: "Đường trơn trượt",
    24: "Đường hẹp (phải)",
    25: "Công trường",
    26: "Đèn tín hiệu giao thông",
    27: "Đường người đi bộ",
    28: "Trẻ em qua đường",
    29: "Đường xe đạp",
    30: "Cẩn thận băng tuyết",
    31: "Thú rừng qua đường",
    32: "Hết tất cả lệnh cấm",
    33: "Rẽ phải",
    34: "Rẽ trái",
    35: "Đi thẳng",
    36: "Đi thẳng hoặc rẽ phải",
    37: "Đi thẳng hoặc rẽ trái",
    38: "Giữ bên phải",
    39: "Giữ bên trái",
    40: "Vòng xuyến",
    41: "Hết cấm vượt",
    42: "Hết cấm xe tải vượt",
}

_MANDATORY = {VIETNAMESE_CLASSES[class_id] for class_id in range(33, 41)}


def alert_sentence(label: str) -> str:
    """Turn a displayed Vietnamese label into a spoken sentence."""
    if label.endswith("km/h)"):
        label = label.replace(" (", " ").replace("km/h)", " ki lô mét trên giờ")
    label = label.replace(" (Stop)", "").replace("3.5", "3 phẩy 5")
    label = label.replace(" (", " ").replace(")", "")
    if label in _MANDATORY:
        prefix = "biển hiệu lệnh"
    elif label.startswith("Cấm ") or label in ("Nhường đường", "Dừng lại"):
        prefix = "biển"
    else:
        prefix = "biển báo"
    return f"Phía trước có {prefix} {label.lower()}."
