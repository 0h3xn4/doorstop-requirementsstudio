"""ReqIF 1.0/1.2 exchange (OMG Requirements Interchange Format) for specifications and their links.

Export: one SPECIFICATION per document (hierarchy by item level), one SPEC-OBJECT per item (a single object type
carrying every attribute of the project templates), SPEC-RELATIONs for parent links and the typed links of
``config/links.yaml``. The statement is written twice: as XHTML (``ReqIF.Text``, what other tools show) and as the
original Markdown (``RVS.Markdown``, what RVS reads back), so RVS -> ReqIF -> RVS is lossless.

Import: ``read_reqif`` converts a file into the same row dictionaries the CSV/XLSX import uses, so the existing
dry-run, validation, history and reason rules apply unchanged. Files from other tools work too: attributes are matched
by name (or by an explicit mapping), unknown ones are reported, objects without an RVS ID get the next free IDs.

Safety: files containing DOCTYPE/entity declarations are refused (entity expansion attacks); nothing is fetched.
Not validated against the official XSD (it is not available offline); structure follows ReqIF 1.2 element order.
"""

import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import markdown

from rvs_core import textcheck
from rvs_core.adapter import ItemData
from rvs_core.config import ProjectConfig
from rvs_core.config.model import AttributeDef
from rvs_core.exporters.itemsio import HIDDEN_ATTRIBUTES, encode, item_columns
from rvs_core.matrices.provenance import Provenance

NS = "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"
XHTML = "http://www.w3.org/1999/xhtml"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
Q = f"{{{NS}}}"
_UID = re.compile(r"^([A-Z][A-Z0-9]*)-(\d+)$")
_SPACES = re.compile(r"[\s\-]+")

# attribute definitions every export carries (id suffix, ReqIF long name, datatype)
CORE_ATTRIBUTES = (
    ("ForeignID", "ReqIF.ForeignID", "string"),
    ("Markdown", "RVS.Markdown", "string"),
    ("Text", "ReqIF.Text", "xhtml"),
    ("Level", "RVS.Level", "string"),
    ("Header", "RVS.Header", "string"),
    ("Normative", "RVS.Normative", "boolean"),
    ("Derived", "RVS.Derived", "boolean"),
    ("Active", "RVS.Active", "boolean"),
    ("Ref", "RVS.Ref", "string"),
    ("Parents", "RVS.Parents", "string"),
)
RELATION_PARENT = "parent"
_NAME_TO_COLUMN = {
    "reqif.text": "text", "rvs.markdown": "text", "reqif.chaptername": "title", "reqif.name": "title",
    "rvs.level": "level", "rvs.header": "header", "rvs.normative": "normative", "rvs.derived": "derived",
    "rvs.active": "active", "rvs.ref": "ref", "reqif.foreignid": "id", "rvs.parents": "parents",
}  # fmt: skip


def _e(tag: str, parent: ET.Element | None = None, text: str | None = None, **attrs: str) -> ET.Element:
    attrs = {k: textcheck.clean(v) for k, v in attrs.items()}  # XML 1.0 cannot hold most control characters
    element = ET.Element(Q + tag, attrs) if parent is None else ET.SubElement(parent, Q + tag, attrs)
    if text is not None:
        element.text = textcheck.clean(text)
    return element


def _ref(parent: ET.Element, wrapper: str, tag: str, target: str) -> None:
    _e(tag, _e(wrapper, parent), target)


# export #########################################################################################################
def _xhtml_div(text: str) -> ET.Element:
    """Markdown -> XHTML div. Raw HTML in a statement is shown as text, never interpreted."""
    text = textcheck.clean(text)
    escaped = text.replace("&", "&amp;").replace("<", "&lt;")
    html = markdown.markdown(escaped, extensions=["sane_lists"], output_format="xhtml")
    try:
        div = ET.fromstring(f'<div xmlns="{XHTML}">{html}</div>')  # noqa: S314 - our own markup, no entities
    except ET.ParseError:
        div = ET.Element(f"{{{XHTML}}}div")
        ET.SubElement(div, f"{{{XHTML}}}p").text = text
    for element in div.iter():  # a link or image in a statement must not carry a script or data URL into other tools
        for attribute in ("href", "src"):
            target = element.get(attribute, "")
            if target and not re.match(r"^(https?:|mailto:|#|[^:/]*(/|$))", target.strip(), re.IGNORECASE):
                del element.attrib[attribute]
    return div


def _attribute_columns(cfg: ProjectConfig) -> list[AttributeDef]:
    """Template attributes carried as plain attributes (links become relations, the schema version is internal)."""
    seen: dict[str, AttributeDef] = {}
    for kind in ("requirements", "verification"):
        for adef in list(cfg.templates.kinds[kind].attributes) + list(cfg.project.free_attributes):
            if adef.name in HIDDEN_ATTRIBUTES or adef.name in seen:
                continue
            seen[adef.name] = adef
    return list(seen.values())


def _datatype_for(adef: AttributeDef) -> str:
    return {"enum": "enum", "int": "integer"}.get(adef.type, "string")


def export_reqif(
    cfg: ProjectConfig, items: Sequence[ItemData], prov: Provenance, documents: Sequence[str] = ()
) -> bytes:
    stamp = prov.generated.strftime("%Y-%m-%dT%H:%M:%S")
    wanted = [d for d in cfg.project.documents if not documents or d.prefix in documents]
    prefixes = {d.prefix for d in wanted}
    order = {d.prefix: n for n, d in enumerate(cfg.project.documents)}
    chosen = sorted(
        (i for i in items if i.document in prefixes), key=lambda i: (order.get(i.document, 999), i.level_key, i.uid)
    )
    uids = {i.uid for i in chosen}
    attrs = _attribute_columns(cfg)
    title_def = next((a for a in attrs if a.name == "title"), None)

    ET.register_namespace("", NS)
    ET.register_namespace("xhtml", XHTML)
    root = ET.Element(Q + "REQ-IF", {XML_LANG: "en"})
    header = _e("REQ-IF-HEADER", _e("THE-HEADER", root), IDENTIFIER="RVS-HEADER")
    _e("COMMENT", header, "; ".join(line for line in prov.lines()[:2] + prov.lines()[3:]))
    _e("CREATION-TIME", header, stamp)
    _e("REQ-IF-TOOL-ID", header, f"rvs {prov.tool_version}")
    _e("REQ-IF-VERSION", header, "1.0")
    _e("SOURCE-TOOL-ID", header, "rvs")
    _e("TITLE", header, prov.project)
    content = _e("REQ-IF-CONTENT", _e("CORE-CONTENT", root))

    def ident(tag: str, parent: ET.Element, identifier: str, name: str | None = None, **extra: str) -> ET.Element:
        a = {"IDENTIFIER": identifier, "LAST-CHANGE": stamp, **extra}
        if name is not None:
            a["LONG-NAME"] = name
        return _e(tag, parent, **a)

    # datatypes
    types = _e("DATATYPES", content)
    ident("DATATYPE-DEFINITION-STRING", types, "RVS-DT-String", "String", **{"MAX-LENGTH": "32000"})
    ident("DATATYPE-DEFINITION-XHTML", types, "RVS-DT-XHTML", "XHTML")
    ident("DATATYPE-DEFINITION-BOOLEAN", types, "RVS-DT-Boolean", "Boolean")
    ident("DATATYPE-DEFINITION-INTEGER", types, "RVS-DT-Integer", "Integer", MIN="-2147483648", MAX="2147483647")
    enum_ids: dict[tuple[str, str], str] = {}
    for vocab in sorted({a.vocab for a in attrs if a.type == "enum" and a.vocab}):  # type: ignore[type-var,unused-ignore]
        enum = ident("DATATYPE-DEFINITION-ENUMERATION", types, f"RVS-DT-Enum-{vocab}", vocab)
        specified = _e("SPECIFIED-VALUES", enum)
        known = list(cfg.vocab.values(vocab))
        stray = sorted(  # values in use that the vocabulary does not list: kept, so no information is lost
            {
                str(i.attrs[a.name])
                for i in chosen
                for a in attrs
                if a.type == "enum" and a.vocab == vocab and i.attrs.get(a.name) not in (None, "")
            }
            - set(known)
        )
        for n, value in enumerate([*known, *stray]):
            enum_ids[(vocab, value)] = f"RVS-EV-{vocab}-{n}"
            ev = ident("ENUM-VALUE", specified, enum_ids[(vocab, value)], value)
            _e("EMBEDDED-VALUE", _e("PROPERTIES", ev), KEY=str(n), **{"OTHER-CONTENT": ""})

    # object type with all attribute definitions
    spec_types = _e("SPEC-TYPES", content)
    object_type = ident("SPEC-OBJECT-TYPE", spec_types, "RVS-SOT-Item", "RVS item")
    definitions = _e("SPEC-ATTRIBUTES", object_type)
    datatype_ref = {
        "string": ("ATTRIBUTE-DEFINITION-STRING", "DATATYPE-DEFINITION-STRING-REF", "RVS-DT-String"),
        "xhtml": ("ATTRIBUTE-DEFINITION-XHTML", "DATATYPE-DEFINITION-XHTML-REF", "RVS-DT-XHTML"),
        "boolean": ("ATTRIBUTE-DEFINITION-BOOLEAN", "DATATYPE-DEFINITION-BOOLEAN-REF", "RVS-DT-Boolean"),
        "integer": ("ATTRIBUTE-DEFINITION-INTEGER", "DATATYPE-DEFINITION-INTEGER-REF", "RVS-DT-Integer"),
    }

    def define(key: str, name: str, datatype: str, vocab: str | None = None) -> None:
        if datatype == "enum":
            element = ident("ATTRIBUTE-DEFINITION-ENUMERATION", definitions, f"RVS-AD-{key}", name, **{"MULTI-VALUED": "false"})  # fmt: skip
            _ref(element, "TYPE", "DATATYPE-DEFINITION-ENUMERATION-REF", f"RVS-DT-Enum-{vocab}")
            return
        tag, ref_tag, target = datatype_ref[datatype]
        element = ident(tag, definitions, f"RVS-AD-{key}", name)
        _ref(element, "TYPE", ref_tag, target)

    for key, name, datatype in CORE_ATTRIBUTES:
        define(key, name, datatype)
    for adef in attrs:
        if adef is title_def:
            define("title", "ReqIF.ChapterName", "string")
        else:
            define(adef.name, adef.name, _datatype_for(adef), adef.vocab)
    relation_names = [RELATION_PARENT, *[t.name for t in cfg.links.values()]]
    for name in relation_names:
        ident("SPEC-RELATION-TYPE", spec_types, f"RVS-RT-{name}", name)
    ident("SPECIFICATION-TYPE", spec_types, "RVS-ST-Document", "RVS document")

    # objects
    xhtml_slots: list[tuple[ET.Element, str]] = []
    objects = _e("SPEC-OBJECTS", content)
    for item in chosen:
        obj = ident("SPEC-OBJECT", objects, f"RVS-SO-{item.uid}", item.uid)
        _ref(obj, "TYPE", "SPEC-OBJECT-TYPE-REF", "RVS-SOT-Item")
        values = _e("VALUES", obj)

        def put(
            key: str, value: str, datatype: str = "string", vocab: str | None = None, _values: ET.Element = values
        ) -> None:  # noqa: E501
            if datatype == "enum":
                target = enum_ids.get((vocab or "", value))
                if target is None:
                    return  # outside the vocabulary: cannot be represented as an enumeration value
                v = _e("ATTRIBUTE-VALUE-ENUMERATION", _values)
                _ref(v, "DEFINITION", "ATTRIBUTE-DEFINITION-ENUMERATION-REF", f"RVS-AD-{key}")
                _e("ENUM-VALUE-REF", _e("VALUES", v), target)
                return
            tag = {"string": "STRING", "boolean": "BOOLEAN", "integer": "INTEGER", "xhtml": "XHTML"}[datatype]
            if datatype == "xhtml":
                v = _e("ATTRIBUTE-VALUE-XHTML", _values)
                _ref(v, "DEFINITION", "ATTRIBUTE-DEFINITION-XHTML-REF", f"RVS-AD-{key}")
                xhtml_slots.append((_e("THE-VALUE", v), value))
                return
            v = _e(f"ATTRIBUTE-VALUE-{tag}", _values, **{"THE-VALUE": value})
            _ref(v, "DEFINITION", f"ATTRIBUTE-DEFINITION-{tag}-REF", f"RVS-AD-{key}")

        text = item.text.strip()
        put("ForeignID", item.uid)
        put("Markdown", text)
        put("Text", text, "xhtml")
        put("Level", item.level)
        put("Header", item.header)
        put("Normative", "true" if item.normative else "false", "boolean")
        put("Derived", "true" if item.derived else "false", "boolean")
        put("Active", "true" if item.active else "false", "boolean")
        put("Ref", item.ref)
        if item.links:
            put("Parents", ", ".join(item.links))
        for adef in attrs:
            raw = item.attrs.get(adef.name)
            if raw in (None, "", []):
                continue
            key = "title" if adef is title_def else adef.name
            put(key, encode(raw, adef), _datatype_for(adef), adef.vocab)

    # relations: item order, then link type order, then the stored order of the targets
    relations = _e("SPEC-RELATIONS", content)
    count = 0

    def relate(kind: str, source: str, target: str) -> None:
        nonlocal count
        if target not in uids:
            return  # points outside the exported documents
        count += 1
        rel = ident("SPEC-RELATION", relations, f"RVS-SR-{count}")
        _ref(rel, "TYPE", "SPEC-RELATION-TYPE-REF", f"RVS-RT-{kind}")
        _ref(rel, "SOURCE", "SPEC-OBJECT-REF", f"RVS-SO-{source}")
        _ref(rel, "TARGET", "SPEC-OBJECT-REF", f"RVS-SO-{target}")

    for item in chosen:
        for parent in item.links:
            relate(RELATION_PARENT, item.uid, parent)
        for link in cfg.links.values():
            for target in item.attrs.get(link.attribute) or []:
                relate(link.name, item.uid, str(target))

    # specifications: nesting follows the dotted level
    specs = _e("SPECIFICATIONS", content)
    for decl in wanted:
        spec = ident("SPECIFICATION", specs, f"RVS-SP-{decl.prefix}", decl.prefix, DESC=decl.title)
        _ref(spec, "TYPE", "SPECIFICATION-TYPE-REF", "RVS-ST-Document")
        stack: list[tuple[int, ET.Element]] = [(0, _e("CHILDREN", spec))]
        for item in (i for i in chosen if i.document == decl.prefix):
            parts = [p for p in item.level.split(".") if p != ""]
            while len(parts) > 1 and parts[-1] == "0":
                parts.pop()  # "2.0" is a heading at depth 1
            depth = max(1, len(parts))
            while len(stack) > 1 and stack[-1][0] >= depth:
                stack.pop()
            node = ident("SPEC-HIERARCHY", stack[-1][1], f"RVS-SH-{item.uid}")
            _ref(node, "OBJECT", "SPEC-OBJECT-REF", f"RVS-SO-{item.uid}")
            stack.append((depth, _e("CHILDREN", node)))

    ET.indent(root, space="  ")
    for slot, value in xhtml_slots:  # after indenting, so inline XHTML spacing is untouched
        slot.append(_xhtml_div(value))
    for empty in [e for e in root.iter(Q + "CHILDREN") if len(e) == 0]:
        empty.text = None
    return bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True)) + b"\n"


# import #########################################################################################################
@dataclass
class ReqifRead:
    rows: list[dict[str, str]]
    notes: list[str] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)


def _attr(element: ET.Element, name: str) -> str:
    return element.get(name) or ""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in element if _local(c.tag) == name]


def _child(element: ET.Element, name: str) -> ET.Element | None:
    found = _children(element, name)
    return found[0] if found else None


def _find_all(element: ET.Element, name: str) -> list[ET.Element]:
    return [e for e in element.iter() if _local(e.tag) == name]


def _ref_text(element: ET.Element, wrapper: str) -> str:
    box = _child(element, wrapper)
    return ((box[0].text or "").strip()) if box is not None and len(box) else ""


def xhtml_to_markdown(div: ET.Element) -> str:
    """A readable Markdown rendering of an XHTML value (other tools' statements; RVS's own use RVS.Markdown)."""
    out: list[str] = []

    def walk(el: ET.Element, ordered: bool = False, index: list[int] | None = None) -> None:
        name = _local(el.tag)
        if name in ("b", "strong"):
            out.append("**")
        elif name in ("i", "em"):
            out.append("*")
        elif name == "code":
            out.append("`")
        elif name == "li":
            out.append(f"{index[0]}. " if ordered and index else "- ")
            if ordered and index:
                index[0] += 1
        elif name == "br":
            out.append("\n")
        if el.text:
            out.append(el.text if name not in ("ul", "ol") else "")
        counter = [1]
        for child in el:
            walk(child, name == "ol" or (ordered and name == "li"), counter if name == "ol" else index)
            if child.tail:
                out.append(child.tail)
        if name in ("b", "strong"):
            out.append("**")
        elif name in ("i", "em"):
            out.append("*")
        elif name == "code":
            out.append("`")
        elif name in ("p", "div", "h1", "h2", "h3", "h4", "table", "tr") and out and not out[-1].endswith("\n\n"):
            out.append("\n\n")
        elif name == "li":
            out.append("\n")

    walk(div)
    text = "".join(out)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


MAX_HIERARCHY_DEPTH = 100


def _place(
    box: ET.Element | None,
    prefix: str,
    values: Mapping[str, object],
    placed: dict[str, tuple[str, str]],
    order: list[str],
    path: list[int],
) -> None:
    """Walk a SPEC-HIERARCHY: each object gets the document ``prefix`` and its dotted position as level."""
    if len(path) >= MAX_HIERARCHY_DEPTH:
        raise ValueError(f"The ReqIF specification is nested more than {MAX_HIERARCHY_DEPTH} levels deep.")
    for number, node in enumerate(_children(box, "SPEC-HIERARCHY") if box is not None else [], start=1):
        here = [*path, number]
        oid = _ref_text(node, "OBJECT")
        if oid in values and oid not in placed:
            placed[oid] = (prefix, ".".join(str(n) for n in here))
            order.append(oid)
        _place(_child(node, "CHILDREN"), prefix, values, placed, order, here)


def _normal(name: str) -> str:
    return _SPACES.sub("_", name.strip().lower())


def _parse(data: bytes) -> ET.Element:
    if not data.strip():
        raise ValueError("The ReqIF file is empty.")
    variants = [data.lower()]
    for encoding in ("utf-16", "utf-32"):  # the same declaration spelled in a wider encoding
        variants.append(data.decode(encoding, errors="ignore").lower().encode("utf-8", errors="ignore"))
    if any(b"<!doctype" in v or b"<!entity" in v for v in variants):
        raise ValueError("The ReqIF file contains DOCTYPE or entity declarations, which RVS does not read.")
    try:
        root = ET.fromstring(data)  # noqa: S314 - DOCTYPE/ENTITY declarations were refused above
    except ET.ParseError as exc:
        raise ValueError(f"This is not a readable ReqIF (XML) file: {exc}.") from None
    if _local(root.tag) != "REQ-IF":
        raise ValueError("This is not a ReqIF file: the top-level element is not REQ-IF.")
    return root


def read_reqif(
    data: bytes,
    cfg: ProjectConfig,
    items: Sequence[ItemData],
    *,
    document: str | None = None,
    mapping: Mapping[str, str] | None = None,
) -> ReqifRead:
    try:
        return _read_reqif(data, cfg, items, document=document, mapping=mapping)
    except RecursionError:
        raise ValueError("The ReqIF file is nested too deeply to read.") from None


def _read_reqif(  # noqa: C901 - one linear pass over the ReqIF structure
    data: bytes,
    cfg: ProjectConfig,
    items: Sequence[ItemData],
    *,
    document: str | None = None,
    mapping: Mapping[str, str] | None = None,
) -> ReqifRead:
    root = _parse(data)
    found = _find_all(root, "REQ-IF-CONTENT")
    content = found[0] if found else root
    specs = _find_all(content, "SPECIFICATION")
    if not specs:
        raise ValueError("The ReqIF file has no specifications, so there is nothing to import.")
    notes: list[str] = []
    known_columns = set(item_columns(cfg))
    documents = {d.prefix: d for d in cfg.project.documents}
    by_title = {d.title.lower(): d.prefix for d in cfg.project.documents}
    mapping = dict(mapping or {})
    wrong = [c for c in mapping.values() if c not in known_columns]
    if wrong:
        raise ValueError(
            f"The mapping names unknown column(s): {', '.join(wrong)}. Use the column names of an exported items file."
        )  # noqa: E501
    if document is not None and document not in documents:
        raise ValueError(
            f"The document '{document}' does not exist in this project. Choose one of: {', '.join(documents)}."
        )  # noqa: E501

    # attribute definitions, enumerations, relation types
    attr_name: dict[str, str] = {}
    for el in content.iter():
        if _local(el.tag).startswith("ATTRIBUTE-DEFINITION-") and el.get("IDENTIFIER"):
            attr_name[_attr(el, "IDENTIFIER")] = el.get("LONG-NAME") or _attr(el, "IDENTIFIER")
    enum_label = {_attr(e, "IDENTIFIER"): e.get("LONG-NAME") or _attr(e, "IDENTIFIER") for e in _find_all(content, "ENUM-VALUE")}  # fmt: skip
    relation_type = {_attr(t, "IDENTIFIER"): t.get("LONG-NAME") or _attr(t, "IDENTIFIER") for t in _find_all(content, "SPEC-RELATION-TYPE")}  # fmt: skip

    # object values
    values: dict[str, dict[str, str]] = {}
    for obj in _find_all(content, "SPEC-OBJECT"):
        oid, bag = _attr(obj, "IDENTIFIER"), {}
        box = _child(obj, "VALUES")
        for v in list(box) if box is not None else []:
            kind = _local(v.tag)
            if not kind.startswith("ATTRIBUTE-VALUE-"):
                continue
            name = attr_name.get(_ref_text(v, "DEFINITION"), _ref_text(v, "DEFINITION"))
            if kind.endswith("XHTML"):
                holder = _child(v, "THE-VALUE")
                div = holder[0] if holder is not None and len(holder) else None
                bag[name] = xhtml_to_markdown(div) if div is not None else ""
            elif kind.endswith("ENUMERATION"):
                refs = [(r.text or "").strip() for r in _find_all(v, "ENUM-VALUE-REF")]
                bag[name] = ", ".join(enum_label.get(r, r) for r in refs)
            else:
                raw = v.get("THE-VALUE", "")
                if kind.endswith("BOOLEAN"):
                    raw = "yes" if raw.strip().lower() in ("true", "1") else "no"
                bag[name] = raw
        values[oid] = bag

    # relations
    parent_pairs: list[tuple[str, str]] = []
    typed: dict[str, list[tuple[str, str]]] = {}
    link_by_name = {t.name: t for t in cfg.links.values()}
    ignored: dict[str, int] = {}
    for rel in _find_all(content, "SPEC-RELATION"):
        name = relation_type.get(_ref_text(rel, "TYPE"), _ref_text(rel, "TYPE"))
        src, dst = _ref_text(rel, "SOURCE"), _ref_text(rel, "TARGET")
        if name.lower() == RELATION_PARENT:
            parent_pairs.append((src, dst))
        elif name in link_by_name:
            typed.setdefault(name, []).append((src, dst))
        else:
            ignored[name or "(unnamed)"] = ignored.get(name or "(unnamed)", 0) + 1
    for name, n in sorted(ignored.items()):
        notes.append(
            f"{n} relation(s) of type '{name}' were not imported: RVS knows the link types {', '.join(['parent', *link_by_name])}."
        )  # noqa: E501

    # specifications -> documents, hierarchy -> levels
    placed: dict[str, tuple[str, str]] = {}  # object id -> (document, level)
    order: list[str] = []
    for spec in specs:
        title = spec.get("LONG-NAME") or _attr(spec, "IDENTIFIER")
        prefix = (
            document
            or next((p for p in documents if p.lower() == title.strip().lower()), None)
            or by_title.get(title.strip().lower())
        )  # noqa: E501
        if prefix is None:
            raise ValueError(
                f"The ReqIF specification '{title}' does not match a document of this project "
                f"({', '.join(documents)}). Tell RVS which document to import it into."
            )
        _place(_child(spec, "CHILDREN"), prefix, values, placed, order, [])
    orphans = [o for o in values if o not in placed]
    if orphans:
        notes.append(f"{len(orphans)} object(s) are in no specification and were not imported.")

    # ids: keep RVS ids, assign the next free numbers to the rest
    existing_numbers: dict[str, int] = {}
    for i in items:
        m = _UID.match(i.uid)
        if m:
            existing_numbers[m.group(1)] = max(existing_numbers.get(m.group(1), 0), int(m.group(2)))
    kept: dict[str, str] = {}
    for oid in order:
        foreign = values[oid].get("ReqIF.ForeignID", "").strip()
        m = _UID.match(foreign)
        if m and m.group(1) == placed[oid][0]:
            kept[oid] = foreign
            existing_numbers[m.group(1)] = max(existing_numbers.get(m.group(1), 0), int(m.group(2)))
    new_id: dict[str, str] = {}
    for oid in order:
        if oid in kept:
            new_id[oid] = kept[oid]
            continue
        prefix = placed[oid][0]
        existing_numbers[prefix] = existing_numbers.get(prefix, 0) + 1
        new_id[oid] = (
            f"{prefix}{cfg.numbering.sep_for(prefix)}{existing_numbers[prefix]:0{cfg.numbering.digits_for(prefix)}d}"  # noqa: E501
        )

    # parents and typed links per row
    parents: dict[str, list[str]] = {}
    for src, dst in parent_pairs:
        if src in new_id and dst in new_id:
            if placed[src][0] == placed[dst][0]:
                notes.append(f"A parent relation inside the same document ({placed[src][0]}) was not imported.")
            else:
                parents.setdefault(src, []).append(new_id[dst])
    links: dict[tuple[str, str], list[str]] = {}
    for name, pairs in typed.items():
        for src, dst in pairs:
            if src in new_id and dst in new_id:
                links.setdefault((src, name), []).append(new_id[dst])

    # rows
    unmapped: list[str] = []
    rows: list[dict[str, str]] = []
    column_set: list[str] = []
    for n, oid in enumerate(order, start=1):
        doc, derived_level = placed[oid]
        row: dict[str, str] = {"_row": str(n), "id": new_id[oid], "document": doc, "level": derived_level}
        for name, value in values[oid].items():
            column = mapping.get(name) or _NAME_TO_COLUMN.get(name.lower())
            if column is None and _normal(name) in known_columns:
                column = _normal(name)
            if column is None:
                if name not in unmapped:
                    unmapped.append(name)
                continue
            if column == "id":
                continue
            if column == "text" and name.lower() == "reqif.text" and "RVS.Markdown" in values[oid]:
                continue  # prefer the lossless Markdown
            if len(value) > 10 and re.match(r"^\d{4}-\d{2}-\d{2}T", value) and column == "executed_on":
                value = value[:10]
            adef = cfg.attribute_defs(documents[doc].kind).get(column)
            exact = adef is not None and adef.type in ("string", "text")  # stored text keeps its own whitespace
            row[column] = value if exact else value.strip()
        defs = cfg.attribute_defs(documents[doc].kind)
        # An RVS file carries parents and links as attributes (exact, even for a partial export); other tools' files
        # only have relations, and only when the file has relations of a kind is it taken to describe that kind.
        for link_name, tdef in link_by_name.items():
            if tdef.attribute in defs and tdef.attribute not in row and typed.get(link_name):
                row[tdef.attribute] = ", ".join(links.get((oid, link_name), []))
        if "parents" not in row and parent_pairs:
            row["parents"] = ", ".join(sorted(parents.get(oid, [])))
        rows.append(row)
        for c in row:
            if c not in column_set and not c.startswith("_"):
                column_set.append(c)
    for row in rows:  # every row has every column, so a missing value means "empty" like in a CSV
        for c in column_set:
            row.setdefault(c, "")
    foreign_kept = sum(1 for o in order if o not in kept)
    if foreign_kept:
        notes.append(f"{foreign_kept} object(s) had no RVS item ID and were given new IDs.")
    return ReqifRead(rows, notes, unmapped)
