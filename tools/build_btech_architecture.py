"""Generate the monochrome architecture diagram embedded in the BTech manuscript."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "paper" / "assets" / "btech_architecture.png"
WIDTH, HEIGHT = 2400, 930


def font(size: int, bold: bool = False):
    family = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(family, size)


def centered(draw, box, title, subtitle):
    x1, y1, x2, y2 = box
    title_font = font(38, True)
    subtitle_font = font(28)
    title_box = draw.textbbox((0, 0), title, font=title_font)
    subtitle_box = draw.multiline_textbbox((0, 0), subtitle, font=subtitle_font, spacing=8, align="center")
    total_height = title_box[3] - title_box[1] + 18 + subtitle_box[3] - subtitle_box[1]
    y = y1 + (y2 - y1 - total_height) / 2
    draw.text(((x1 + x2) / 2, y), title, fill="black", font=title_font, anchor="ma")
    draw.multiline_text(((x1 + x2) / 2, y + 58), subtitle, fill="black", font=subtitle_font, anchor="ma", spacing=8, align="center")


def arrow(draw, start, end, width=5):
    draw.line((start, end), fill="black", width=width)
    x, y = end
    draw.polygon([(x, y), (x - 24, y - 14), (x - 24, y + 14)], fill="black")


def main():
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    boxes = [
        (60, 110, 440, 360, "Dados", "B3, CVM e\npolítica"),
        (520, 110, 900, 360, "Validação", "datas, cobertura\ne elegibilidade"),
        (980, 110, 1360, 360, "Cálculo", "ranking, pesos\ne custos"),
        (1440, 110, 1820, 360, "Revisão humana", "aceitar, recusar\nou justificar"),
        (1900, 110, 2340, 360, "Dossiê", "fontes, regra, decisão\ne responsável"),
    ]
    for x1, y1, x2, y2, title, subtitle in boxes:
        draw.rounded_rectangle((x1, y1, x2, y2), radius=24, outline="black", width=5)
        centered(draw, (x1, y1, x2, y2), title, subtitle)
    for left, right in zip(boxes, boxes[1:]):
        arrow(draw, (left[2] + 15, 235), (right[0] - 15, 235))

    llm = (1250, 560, 1950, 810)
    draw.rounded_rectangle(llm, radius=24, outline="black", width=5)
    centered(draw, llm, "Modelo de linguagem", "redige tese, riscos e perguntas\na partir de fatos aprovados")
    draw.line((1630, 375, 1630, 535), fill="black", width=5)
    draw.polygon([(1630, 560), (1616, 532), (1644, 532)], fill="black")
    draw.line((1950, 685, 2200, 685, 2200, 385), fill="black", width=5)
    draw.polygon([(2200, 360), (2186, 388), (2214, 388)], fill="black")
    draw.line((1170, 375, 1170, 520), fill="black", width=4)
    draw.line((1135, 450, 1205, 520), fill="black", width=5)
    draw.line((1205, 450, 1135, 520), fill="black", width=5)
    draw.text((880, 488), "sem acesso aos pesos", fill="black", font=font(27), anchor="ma")

    draw.text((WIDTH / 2, 40), "Fluxo verificável da decisão", fill="black", font=font(46, True), anchor="ma")
    draw.text((WIDTH / 2, 880), "Cada etapa grava entrada, versão, saída e responsável.", fill="black", font=font(30), anchor="ma")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT, dpi=(300, 300), optimize=True)
    print(OUTPUT)


if __name__ == "__main__":
    main()
