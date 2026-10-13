# -*- coding: utf-8 -*-
"""Fill the approved results template without rebuilding its formatting."""
import os
import re
import zipfile
from io import BytesIO
from xml.dom import minidom

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TEMPLATE = os.path.join(os.path.dirname(__file__), "setupdata",
                        "Lotus Results XLSX.xlsx")


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
    # Keep formatted analytical results (including qualifiers and precision)
    # as literal text; strings beginning with '=' must never become formulas.
    if isinstance(value, (int, float)):
        node = doc.createElementNS(NS, "v")
        node.appendChild(doc.createTextNode(str(value)))
        cell.appendChild(node)
    else:
        cell.setAttribute("t", "inlineStr")
        node = doc.createElementNS(NS, "is")
        content = doc.createElementNS(NS, "t")
        content.setAttribute("xml:space", "preserve")
        content.appendChild(doc.createTextNode(value))
        node.appendChild(content)
        cell.appendChild(node)


def render_results(rows, template=TEMPLATE):
    """Rows contain metadata A:O and results keyed by exact service Title."""
    output = BytesIO()
    with zipfile.ZipFile(template) as source:
        strings_doc = minidom.parseString(source.read("xl/sharedStrings.xml"))
        strings = [text(si) for si in strings_doc.getElementsByTagName("si")]
        doc = minidom.parseString(source.read("xl/worksheets/sheet1.xml"))
        data = doc.getElementsByTagName("sheetData")[0]
        template_rows = data.getElementsByTagName("row")
        header = next(row for row in template_rows
                      if row.getAttribute("r") == "3")
        columns = {}
        for cell in header.getElementsByTagName("c"):
            values = cell.getElementsByTagName("v")
            if values and cell.getAttribute("t") == "s":
                title = strings[int(text(values[0]))]
                if title in columns:
                    raise ValueError("Duplicate AS Title in results template: " + title)
                columns[title] = column(cell)
        style_row = next(row for row in template_rows
                         if row.getAttribute("r") == "4")
        prototype = style_row.cloneNode(deep=True)
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
            values.update((columns[title], value)
                          for title, value in record["results"].items())
            for cell in row.getElementsByTagName("c"):
                letter = column(cell)
                cell.setAttribute("r", letter + str(index))
                set_value(doc, cell, values.get(letter))
            data.appendChild(row)
        last = max(3, len(rows) + 3)
        for node in doc.getElementsByTagName("dimension"):
            node.setAttribute("ref", "A1:CX{}".format(last))
        for node in doc.getElementsByTagName("autoFilter"):
            node.setAttribute("ref", "B3:CX{}".format(last))
        workbook = minidom.parseString(source.read("xl/workbook.xml"))
        for node in workbook.getElementsByTagName("definedName"):
            if node.getAttribute("name") == "_xlnm._FilterDatabase":
                for child in list(node.childNodes):
                    node.removeChild(child)
                node.appendChild(workbook.createTextNode(
                    "Reporting!$B$3:$CX${}".format(last)))
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
            for entry in source.infolist():
                content = source.read(entry.filename)
                if entry.filename == "xl/worksheets/sheet1.xml":
                    content = doc.toxml(encoding="UTF-8")
                elif entry.filename == "xl/workbook.xml":
                    content = workbook.toxml(encoding="UTF-8")
                target.writestr(entry, content)
    return output.getvalue()
