# -*- coding: utf-8 -*-
"""令和6年7月6日付「御見積書」（有限会社福井工業 → 株式会社竹中工務店）をベースに、
発行日を令和8年9月8日、ツゲの数量を25本→35本、各単価を1.1倍にした見積書を生成する。

元PDFのレイアウト・書体・社印はそのまま流用し、変更のある数値だけを差し替える。
"""
import pymupdf

SRC = "estimate-fukui-planting-20240706-original.pdf"
DST = "estimate-fukui-planting-20260908.pdf"
FONT = "/tmp/_estimate_font.ttf"

# 単価は元単価の1.1倍（端数なし）、数量はツゲのみ25→35本
# ツゲ関連（撤去・購入費）は1.1倍後の金額をさらに1.5倍、腐葉土購入費は2倍にする
ITEMS = [
    # (品名, 数量, 単価)
    ("ツゲ撤去",     35.0,   825),   # 1.1倍の550をさらに1.5倍
    ("土撤去",        1.3, 16500),
    ("土入れ",        1.0, 77000),
    ("植栽手入れ",    1.0, 73700),
    ("ツゲ購入費",   35.0,  4125),   # 1.1倍の2,750をさらに1.5倍
    ("腐葉土購入費",  1.0, 22000),   # 1.1倍の11,000をさらに2倍
]
OVERHEAD_RATE = 0.12          # 諸経費・法定福利費（元見積 28,980 / 241,500 = 12%）
ROUND_UNIT = 1000             # 合計は1,000円未満を切り捨て（元見積の端数調整と同じ考え方）


def money(n):
    return f"{n:,}"


def main():
    subtotal = sum(round(q * u) for _, q, u in ITEMS)
    overhead = round(subtotal * OVERHEAD_RATE)
    total = (subtotal + overhead) // ROUND_UNIT * ROUND_UNIT
    adjust = total - (subtotal + overhead)

    doc = pymupdf.open(SRC)
    page = doc[0]

    # 元PDFに埋め込まれた書体をそのまま使う
    font_xref = page.get_fonts(full=True)[0][0]
    with open(FONT, "wb") as f:
        f.write(doc.extract_font(font_xref)[3])
    font = pymupdf.Font(fontfile=FONT)

    amounts = [round(q * u) for _, q, u in ITEMS]
    # (元の文字列, 新しい文字列, 基準位置, 揃え)  align: "l"=左揃え / "r"=右揃え
    edits = [
        ("令和6年　7月　6日", "令和8年　9月　8日", 10.8, "l"),
        ("¥270,000",     "¥" + money(total), 16.2, "l"),
        # 明細行（数量・単価・金額）
        ("25.00",  f"{ITEMS[0][1]:.2f}", 10.8, "r"),
        ("500",    money(ITEMS[0][2]),   10.8, "r"),
        ("12,500", money(amounts[0]),    10.8, "r"),
        ("15,000", money(ITEMS[1][2]),   10.8, "r"),
        ("19,500", money(amounts[1]),    10.8, "r"),
        ("70,000", money(ITEMS[2][2]),   10.8, "r"),  # 単価・金額とも同額
        ("67,000", money(ITEMS[3][2]),   10.8, "r"),
        ("2,500",  money(ITEMS[4][2]),   10.8, "r"),
        ("62,500", money(amounts[4]),    10.8, "r"),
        ("10,000", money(ITEMS[5][2]),   10.8, "r"),
        # 集計行
        ("241,500", money(subtotal), 10.8, "r"),
        ("-480",    str(adjust),     10.8, "r"),
        ("28,980",  money(overhead), 10.8, "r"),
        ("270,000", money(total),    10.8, "r"),
    ]

    spans = [s for b in page.get_text("dict")["blocks"]
             for l in b.get("lines", []) for s in l["spans"]]

    # 置換対象のspanを元テキストで引き当てる（同一文字列が複数ある場合はすべて置換）
    targets = []
    for old, new, size, align in edits:
        hits = [s for s in spans if s["text"] == old]
        if not hits:
            raise SystemExit(f"元PDFに '{old}' が見つかりません")
        for s in hits:
            targets.append((s, new, size, align))

    # 旧文字列を消す（描画を白で覆うのではなくテキストごと削除する）
    for s, _, _, _ in targets:
        x0, y0, x1, y1 = s["bbox"]
        page.add_redact_annot(pymupdf.Rect(x0 - 0.5, y0 - 0.5, x1 + 0.5, y1 + 0.5),
                              fill=False)  # 罫線・セル塗りを壊さないよう塗り潰しはしない
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                          graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                          text=pymupdf.PDF_REDACT_TEXT_REMOVE)

    # 新文字列を同じ書体・サイズ・色で書き込む
    for s, new, size, align in targets:
        x, y = s["origin"]
        if align == "r":
            right = s["bbox"][2]
            x = right - font.text_length(new, fontsize=size)
        color = ((s["color"] >> 16) / 255, ((s["color"] >> 8) & 255) / 255,
                 (s["color"] & 255) / 255)
        page.insert_text((x, y), new, fontname="EST", fontfile=FONT,
                         fontsize=size, color=color)

    doc.save(DST, garbage=4, deflate=True)
    print(f"小計 {subtotal:,} / 端数調整 {adjust} / 諸経費 {overhead:,} / 合計 {total:,}")
    print("->", DST)


if __name__ == "__main__":
    main()
