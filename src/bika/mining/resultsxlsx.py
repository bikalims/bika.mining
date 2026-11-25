# -*- coding: utf-8 -*-
"""Fill the approved results template without rebuilding its formatting."""
import os
import re
import zipfile
from datetime import datetime
from io import BytesIO
from xml.dom import minidom

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TEMPLATE = os.path.join(os.path.dirname(__file__), "setupdata",
                        "Bika Lotus Results XLSX COA 03.xlsx")
REPORT_FIELDS = (("A", u"Client"), ("C", u"COA ID"),
                 ("E", u"Date Published"), ("G", u"Published by"),
                 ("I", u"File name"))
DATETIME_COLUMNS = ("J", "K")


def text(node):
    return u"".join(child.data if child.nodeType == child.TEXT_NODE
                    else text(child) for child in node.childNodes)


def column(cell):
    return re.sub(r"\d+$", "", cell.getAttribute("r"))


def set_value(doc, cell, value):
    for child in list(cell.childNodes):
        cell.removeChild(child)
    if cell.hasAttribute("t"):
        cell.removeAttribute("t")
    if value is None or value == "":
        return
    if isinstance(value, datetime):
        # The workbook uses Excel's 1900 date system.
        delta = value - datetime(1899, 12, 30)
        value = delta.total_seconds() / 86400
        if 0 < value < 61:
            value -= 1
    # Keep formatted analytical results (including qualifiers and precision)
    # as literal text; strings beginning with '=' must never become formulas.
    if isinstance(value, (int, float)):
        node = doc.createElementNS(NS, "v")
        node.appendChild(doc.createTextNode(repr(value)))
        cell.appendChild(node)
    else:
        cell.setAttribute("t", "inlineStr")
        node = doc.createElementNS(NS, "is")
        content = doc.createElementNS(NS, "t")
        content.setAttribute("xml:space", "preserve")
        content.appendChild(doc.createTextNode(value))
        node.appendChild(content)
        cell.appendChild(node)


def set_results_fonts(styles, row, size=None):
    """Normalize body fonts, or resize a row while retaining its font style."""
    fonts = styles.getElementsByTagName("fonts")[0]
    formats = styles.getElementsByTagName("cellXfs")[0]
    original_fonts = list(fonts.getElementsByTagName("font"))
    original_formats = list(formats.getElementsByTagName("xf"))
    font_map, format_map = {}, {}
    for cell in row.getElementsByTagName("c"):
        style_id = int(cell.getAttribute("s") or 0)
        datetime_cell = size is None and column(cell) in DATETIME_COLUMNS
        format_key = (style_id, datetime_cell)
        if format_key not in format_map:
            style = original_formats[style_id].cloneNode(deep=True)
            font_id = int(style.getAttribute("fontId") or 0)
            if font_id not in font_map:
                font = original_fonts[font_id].cloneNode(deep=True)
                if size is None:
                    replaced = ("b", "i", "name", "color", "scheme")
                    properties = [("name", "val", "Arial"),
                                  ("color", "rgb", "FF000000")]
                else:
                    replaced = ("sz",)
                    properties = [("sz", "val", str(size))]
                for child in list(font.childNodes):
                    if child.nodeName in replaced:
                        font.removeChild(child)
                for tag, attribute, value in properties:
                    node = styles.createElementNS(NS, tag)
                    node.setAttribute(attribute, value)
                    font.appendChild(node)
                font_map[font_id] = len(fonts.getElementsByTagName("font"))
                fonts.appendChild(font)
            style.setAttribute("fontId", str(font_map[font_id]))
            style.setAttribute("applyFont", "1")
            if datetime_cell:
                style.setAttribute("numFmtId", "22")
                style.setAttribute("applyNumberFormat", "1")
            format_map[format_key] = len(formats.getElementsByTagName("xf"))
            formats.appendChild(style)
        cell.setAttribute("s", str(format_map[format_key]))
    fonts.setAttribute("count", str(len(fonts.getElementsByTagName("font"))))
    formats.setAttribute("count", str(len(formats.getElementsByTagName("xf"))))


def set_report_header(doc, styles, row, heading_row, values):
    cells = row.getElementsByTagName("c")
    heading_style = heading_row.getElementsByTagName("c")[0].getAttribute("s")
    for cell in cells:
        set_value(doc, cell, None)
    for cell in cells[:2 * len(REPORT_FIELDS)]:
        cell.setAttribute("s", heading_style)
    for index, (key, label) in enumerate(REPORT_FIELDS):
        label_cell, value_cell = cells[2 * index:2 * index + 2]
        set_value(doc, label_cell, label)
        set_value(doc, value_cell, values.get(key))
    set_results_fonts(styles, row, size=10)
    # Allow Excel to fit wrapped client and publisher names in row 1.
    row.removeAttribute("ht")
    row.removeAttribute("customHeight")


def render_results(rows, template=TEMPLATE, report_header=None):
    """Rows contain metadata A:O and results keyed by exact service Title."""
    output = BytesIO()
    with zipfile.ZipFile(template) as source:
        strings_doc = minidom.parseString(source.read("xl/sharedStrings.xml"))
        strings = [text(si) for si in strings_doc.getElementsByTagName("si")]
        doc = minidom.parseString(source.read("xl/worksheets/sheet1.xml"))
        data = doc.getElementsByTagName("sheetData")[0]
        template_rows = data.getElementsByTagName("row")
        styles = minidom.parseString(source.read("xl/styles.xml"))
        report_row = next(row for row in template_rows
                          if row.getAttribute("r") == "1")
        heading_row = next(row for row in template_rows
                           if row.getAttribute("r") == "2")
        sample_headings = {
            "A2": u"LIMS sample ID", "C2": u"Plant sample ID",
            "J2": u"Time Transferred", "K2": u"Date and Time Received",
        }
        for cell in heading_row.getElementsByTagName("c"):
            label = sample_headings.get(cell.getAttribute("r"))
            if label is not None:
                set_value(doc, cell, label)
        for definition in doc.getElementsByTagName("col"):
            if definition.getAttribute("max") == "10":
                if definition.getAttribute("min") == "9":
                    shift = definition.cloneNode(deep=True)
                    shift.setAttribute("max", "9")
                    definition.parentNode.insertBefore(shift, definition)
                    definition.setAttribute("min", "10")
                definition.setAttribute("width", "22")
            elif definition.getAttribute("min") == "11":
                definition.setAttribute("width", "22")
        set_report_header(doc, styles, report_row, heading_row, report_header or {})
        header = next(row for row in template_rows
                      if row.getAttribute("r") == "3")
        columns = {}
        for cell in header.getElementsByTagName("c"):
            values = cell.getElementsByTagName("v")
            if values and cell.getAttribute("t") == "s":
                title = strings[int(text(values[0]))]
                # The final chlorine result is a separate service from the
                # earlier Cl result, despite the legacy template header.
                if title == "Cl (ppm)" and title in columns:
                    title = "Cl final (ppm)"
                    set_value(doc, cell, title)
                # A service can appear in more than one report section.
                # Keep every fixed destination for its exact Title.
                columns.setdefault(title, []).append(column(cell))
        last_column = column(header.getElementsByTagName("c")[-1])
        style_row = next(row for row in template_rows
                         if row.getAttribute("r") == "4")
        prototype = style_row.cloneNode(deep=True)
        set_results_fonts(styles, prototype)
        for row in list(template_rows):
            if int(row.getAttribute("r")) >= 4:
                data.removeChild(row)
        for index, record in enumerate(rows, 4):
            unknown = set(record["results"]) - set(columns)
            if unknown:
                raise ValueError("AS Title missing from fixed results template: " +
                                 u", ".join(sorted(unknown)))
            row = prototype.cloneNode(deep=True)
            row.setAttribute("r", str(index))
            values = dict(record["metadata"])
            values.update((destination, value)
                          for title, value in record["results"].items()
                          for destination in columns[title])
            for cell in row.getElementsByTagName("c"):
                letter = column(cell)
                cell.setAttribute("r", letter + str(index))
                set_value(doc, cell, values.get(letter))
            data.appendChild(row)
        last = max(3, len(rows) + 3)
        for node in doc.getElementsByTagName("dimension"):
            node.setAttribute("ref", "A1:{}{}".format(last_column, last))
        for node in doc.getElementsByTagName("autoFilter"):
            node.setAttribute("ref", "B3:{}{}".format(last_column, last))
        workbook = minidom.parseString(source.read("xl/workbook.xml"))
        for node in workbook.getElementsByTagName("definedName"):
            if node.getAttribute("name") == "_xlnm._FilterDatabase":
                for child in list(node.childNodes):
                    node.removeChild(child)
                node.appendChild(workbook.createTextNode(
                    "Reporting!$B$3:${}${}".format(last_column, last)))
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
            for entry in source.infolist():
                content = source.read(entry.filename)
                if entry.filename == "xl/worksheets/sheet1.xml":
                    content = doc.toxml(encoding="UTF-8")
                elif entry.filename == "xl/workbook.xml":
                    content = workbook.toxml(encoding="UTF-8")
                elif entry.filename == "xl/styles.xml":
                    content = styles.toxml(encoding="UTF-8")
                target.writestr(entry, content)
    return output.getvalue()
