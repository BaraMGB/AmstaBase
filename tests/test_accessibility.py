from pathlib import Path


def relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted(
        (relative_luminance(first), relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_core_color_pairs_meet_wcag_aa_for_normal_text():
    pairs = {
        "body text": ("#f8f9fa", "#646669"),
        "links on dark background": ("#dbeafe", "#646669"),
        "card text": ("#343a40", "#ffffff"),
        "secondary card text": ("#495057", "#ffffff"),
        "card links": ("#0056b3", "#ffffff"),
        "navbar text": ("#ffffff", "#343a40"),
        "yellow navbar buttons": ("#212529", "#ffc107"),
        "primary buttons": ("#ffffff", "#0d6efd"),
        "danger buttons": ("#ffffff", "#dc3545"),
    }
    for description, (foreground, background) in pairs.items():
        assert contrast_ratio(foreground, background) >= 4.5, description


def test_accessible_palette_is_present_in_stylesheet():
    stylesheet = Path("amstabase/static/style.css").read_text(encoding="utf-8")
    for color in (
        "#646669",
        "#f8f9fa",
        "#dbeafe",
        "#343a40",
        "#495057",
        "#0056b3",
        "#212529",
    ):
        assert color in stylesheet
