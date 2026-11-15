def add_paragraph(
    blocks: list[dict],
    text: str,
    style: str = "Normal",
) -> None:
    paragraph_number = 1 + sum(block.get("type") == "paragraph" for block in blocks)

    blocks.append(
        {
            "id": f"P{paragraph_number}",
            "type": "paragraph",
            "style": style,
            "text": text,
        }
    )
