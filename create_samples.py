from pathlib import Path

from docx import Document

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "samples"


def create_document(filename: str, include_location: bool) -> None:
    document = Document()
    document.add_heading("ВЕДОМОСТЬ ЭКСПЛУАТАЦИОННЫХ ДОКУМЕНТОВ", level=0)
    document.add_paragraph("Программа «Учёт рабочего времени»")
    document.add_paragraph(
        "Программное изделие является компонентом, "
        "имеющим самостоятельное применение."
    )
    document.add_heading("Документы на программу", level=1)

    headers = ["Обозначение", "Наименование", "Кол. экз."]
    if include_location:
        headers.append("Местонахождение")

    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"

    for index, header in enumerate(headers):
        table.rows[0].cells[index].text = header

    documents = [
        (
            "УРВ.00001-01 31 01",
            "Учёт рабочего времени. Руководство системного программиста",
            "1",
            "Папка № 1",
        ),
        (
            "УРВ.00001-01 32 01",
            "Учёт рабочего времени. Формуляр",
            "1",
            "Папка № 1",
        ),
    ]

    for designation, name, copies, location in documents:
        values = [designation, name, copies]
        if include_location:
            values.append(location)

        cells = table.add_row().cells
        for index, value in enumerate(values):
            cells[index].text = value

    document.save(OUTPUT_DIR / filename)


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    create_document("ведомость_основная.docx", include_location=True)
    create_document("ведомость_с_ошибкой.docx", include_location=False)
    print(f"Тестовые документы созданы в {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
