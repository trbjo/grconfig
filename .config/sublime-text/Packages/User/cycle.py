import contextlib
import itertools
import sublime
import sublime_plugin
import re

from .mock_sublime import (
    View as TextView,
    Region as TextViewRegion
)



LIST_ENTRY_BEGIN_RE = re.compile(
    r"""^(
            \s+[#] |
            \s*[-+] |
            \s*[0-9]+[.] |
            \s[a-zA-Z][.]
        )\s+
        (?:
            (?P<tick_box>\[[- xX]\])
            \s
        )?
        """,
    re.VERBOSE
)
HEADLINE_RE = re.compile(
    '^([#]+) \\s+'  # STARS group 1
    '(?: ([A-Za-z0-9]+)\\s+ )?'  # KEYWORD group 2
    '(?: \\[[#]([a-zA-Z])\\]\\s+)?'  # PRIORITY group 3
    '(.*?)'  # TITLE -- match in nongreedy fashion group 4
    '\\s* (:(?: [a-zA-Z0-9_@#]+ :)+)? \\s*$',  # TAGS group 5
    re.VERBOSE
)
CONTROL_LINE_RE = re.compile(
    "^\#\+"  # prefix
    "([A-Z_]+) :"  # key
    "\s* (.*)",  # value
    re.VERBOSE
)
BEGIN_SRC_RE = re.compile(
    r"^\s*\#\+BEGIN_SRC\b.*$"
)
END_SRC_RE = re.compile(
    r"^\s*\#\+END_SRC\b.*$"
)



BEGIN_EXAMPLE_RE = re.compile(
    r"^\s*\#\+BEGIN_EXAMPLE\b.*$"
)
END_EXAMPLE_RE = re.compile(
    r"^\s*\#\+END_EXAMPLE\b.*$"
)
COLON_LINE_EXAMPLE_RE = re.compile(
    r"^\s*:.*$"
)
KEYWORD_SET = frozenset(["TODO", "CURRENT", "DONE"])


class CycleCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        if len(view.sel()) != 1:
            return
        sel, = view.sel()
        if not sel.empty():
            return

        # - получить строку в которой мы находимся
        current_line_region = view.line(sel)
        current_line_index, _ = view.rowcol(current_line_region.a)
        current_line = view.substr(current_line_region)

        # убедиться, что это headline
        match = re.search(r'^([#]+)\s', current_line)
        if not match:
            return
        current_headline_level = len(match.group(1))
        next_headline_re = '^[#]{{1,{}}}\s'.format(current_headline_level)

        # найти следующий headline того же типа или высшего
        next_headline_region = view.find(next_headline_re, current_line_region.b)
        region_to_fold = sublime.Region(current_line_region.b, next_headline_region.a - 1)
        if region_to_fold.empty():
            return
        if not is_straight_region(region_to_fold):
            region_to_fold = sublime.Region(current_line_region.b, view.size())
        # свернуть
        folded = view.fold(region_to_fold)
        if not folded:
            view.unfold(region_to_fold)


class CycleAllCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        try:
            view = self.view
            view_get_cursor_point(view)

            org_root = parse_org_document_new(view, view_get_full_region(view))

            headline_list = [
                n
                for n in iter_tree_depth_first(org_root)
                if isinstance(n, OrgHeadline)
            ]
            if not headline_list:
                return

            # The first header we see is top header.
            # NOTE: if first header has level > 1 we will show all headers that satisfy condition:
            #   1 <= header_level <= first_header_level
            # Such behaviour complies to Emacs.
            top_headline_max_level = headline_list[0].level
            top_headers_folding = get_folding_for_headers(
                view,
                (h.region for h in headline_list if h.level <= top_headline_max_level)
            )
            all_headers_folding = get_folding_for_headers(view, (h.region for h in headline_list))

            folded_regions = view.folded_regions()
            # folded_links = view.find_by_selector("url.link.text.org")
            # folded_headers = list(set(folded_regions) - set(folded_links))


            view.unfold(folded_regions)
            view.fold(self.view.find_by_selector("url.link.text.org"))
            if folded_regions == all_headers_folding:
                # unfolded region
                pass
            elif folded_regions == top_headers_folding:
                view.fold(all_headers_folding)
            else:
                view.fold(top_headers_folding)
        except ZorgmodeError as e:
            sublime.status_message(str(e))



class ZorgmodeError(RuntimeError):
    pass





def is_straight_region(region_to_fold):
    return region_to_fold.a < region_to_fold.b

def view_get_cursor_point(view):
    if len(view.sel()) == 0:
        raise ZorgmodeError("Cannot run this command with no cursor")
    if len(view.sel()) > 1:
        raise ZorgmodeError("Cannot run this command with multiple cursors")
    sel, = view.sel()
    if not sel.empty():
        raise ZorgmodeError("Cannot run this command with selection")
    return sel.a


def view_get_full_region(v):
    if isinstance(v, TextView):
        cls = TextViewRegion
    else:
        assert isinstance(v, sublime.View)
        cls = sublime.Region
    return cls(0, v.size())

def parse_org_document_new(view, region):
    builder = OrgTreeBuilder(view)
    parser_input = ParserInput(view, region)

    parse_global_scope(parser_input, builder)

    return builder.finish()


class OrgTreeBuilder:
    def __init__(self, view):
        self._root = OrgRoot(view)
        section = OrgSection(view, self._root, 0)
        self._stack = [self._root, section]
        self._context_stack = [2]

    def top(self):
        return self._stack[-1]

    def pop(self):
        self._stack.pop()

    def push(self, node):
        self._stack.append(node)

    def finish(self):
        self._stack = None
        return self._root

    @contextlib.contextmanager
    def push_context(self):
        curlen = len(self._stack)
        self._context_stack.append(curlen)
        yield
        self._context_stack.pop()
        if len(self._stack) > curlen:
            del self._stack[curlen:]

    def is_context_empty(self):
        return len(self._stack) <= self._context_stack[-1]



class OrgViewNode(object):
    def __init__(self, view, parent):
        self.children = []
        self.parent = parent
        if self.parent:
            self.parent.children.append(self)
        self.region = None
        self.view = view

    def text(self):
        return self.view.substr(self.region)

    def __repr__(self):
        text = _node_text(self)
        if len(text) > 55:
            text = "{} ... {}".format(text[:25], text[-25:])
        attrs = self._debug_attrs()
        if attrs != "":
            attrs += ", "
        return "{cls}({attrs}{str_repr})".format(cls=type(self).__name__, attrs=attrs, str_repr=repr(text))

    def _debug_attrs(self):
        return ""

    def debug_print(self, indent=None, file=None):
        if file is None:
            file = sys.stdout
        if indent is None:
            indent = 0
        indent_str = " " * indent
        file.write(indent_str + repr(self) + "\n")
        for c in self.children:
            c.debug_print(indent+2)
        if indent == 0:
            file.flush()






class OrgRoot(OrgViewNode):
    node_type = "root"

    def __init__(self, view):
        super(OrgRoot, self).__init__(view, None)


class OrgSection(OrgViewNode):
    node_type = "section"

    def __init__(self, view, parent, level):
        super(OrgSection, self).__init__(view, parent)
        self.level = level

    def _debug_attrs(self):
        return "level={}".format(self.level)


class ParserInput:
    def __init__(self, view, region):
        self._full_line_region_list = view_full_lines(view, region)
        self._idx = 0
        self.view = view

    def get_current_line_region(self):
        if self._idx < len(self._full_line_region_list):
            return self._full_line_region_list[self._idx]
        else:
            return None

    def next_line(self):
        self._idx += 1


def view_full_lines(view, region):
    # NOTE: line ending might be either '\r\n' or '\n'
    # TODO: test this function
    line_region_list = view.lines(region)
    for i in range(len(line_region_list) - 1):
        line_region_list[i].b = line_region_list[i+1].a
    if line_region_list:
        line_region_list[-1].b = view.size()
    return line_region_list


def parse_global_scope(parser_input: ParserInput, builder: OrgTreeBuilder):
    view = parser_input.view
    while parser_input.get_current_line_region() is not None:
        region = parser_input.get_current_line_region()
        line = view.substr(region)
        line = line.rstrip('\n')
        m = HEADLINE_RE.match(line)
        if m is not None:
            headline_level = len(m.group(1))
            assert headline_level > 0
            while (
                    not isinstance(builder.top(), OrgSection)
                    or builder.top().level >= headline_level
            ):
                builder.pop()

            new_section = OrgSection(view, builder.top(), headline_level)
            headline = OrgHeadline(view, new_section, headline_level)
            builder.push(new_section)
            _extend_region(headline, region)
            parser_input.next_line()
            continue

        m = LIST_ENTRY_BEGIN_RE.match(line)
        if m is not None:
            with builder.push_context():
                parse_list(parser_input, builder)
            continue

        m = BEGIN_SRC_RE.match(line)
        if m is not None:
            with builder.push_context():
                parse_example_block(parser_input, builder, BEGIN_SRC_RE, END_SRC_RE)
            continue

        m = BEGIN_EXAMPLE_RE.match(line)
        if m is not None:
            with builder.push_context():
                parse_example_block(parser_input, builder, BEGIN_EXAMPLE_RE, END_EXAMPLE_RE)
            continue

        m = COLON_LINE_EXAMPLE_RE.match(line)
        if m is not None:
            with builder.push_context():
                parse_example_block(parser_input, builder, COLON_LINE_EXAMPLE_RE, None)

        m = CONTROL_LINE_RE.match(line)
        if m is not None:
            control_line = OrgControlLine(view, builder.top())
            _extend_region(control_line, region)
            parser_input.next_line()
            continue

        _extend_region(builder.top(), region)
        parser_input.next_line()
        continue


class OrgHeadline(OrgViewNode):
    node_type = "headline"

    def __init__(self, view, parent, level):
        super(OrgHeadline, self).__init__(view, parent)
        self.level = level

    def _debug_attrs(self):
        return "level={}".format(self.level)

def _extend_region(node, region):
    # we don't want to be dependent on region class so we'll derive region class from runtime
    region_cls = type(region)
    while node:
        if node.region is None:
            node.region = region
        else:
            new_region = region_cls(node.region.a, region.b)
            node.region = new_region
        node = node.parent


def parse_list(parser_input: ParserInput, builder: OrgTreeBuilder):
    view = parser_input.view
    empty_lines = 0
    while parser_input.get_current_line_region() is not None:
        region = parser_input.get_current_line_region()
        line = view.substr(region)

        if line.startswith("*"):
            break

        line_is_empty = not bool(line.strip())
        if line_is_empty:
            empty_lines += 1
            if empty_lines >= 2:
                return
            parser_input.next_line()
            continue
        else:
            empty_lines = 0

        indent = _calc_indent(line)
        m = LIST_ENTRY_BEGIN_RE.match(line)
        if m is not None:
            while (
                isinstance(builder.top(), OrgList) and builder.top().indent > indent
                or isinstance(builder.top(), OrgListEntry) and builder.top().indent >= indent
            ):
                builder.pop()

            if (
                not isinstance(builder.top(), OrgList)
                or builder.top().indent < indent
            ):
                builder.push(OrgList(view, builder.top(), indent))

            builder.push(OrgListEntry(view, builder.top(), indent, m))
            _extend_region(builder.top(), region)
            parser_input.next_line()
            continue

        while (
            not builder.is_context_empty()
            and not (
                isinstance(builder.top(), OrgListEntry)
                and builder.top().indent < indent
            )
        ):
            builder.pop()

        if builder.is_context_empty():
            return

        assert isinstance(builder.top(), OrgListEntry)
        _extend_region(builder.top(), region)
        parser_input.next_line()


def _calc_indent(line):
    indent = 0
    for c in line:
        if c == ' ':
            indent += 1
        else:
            break
    return indent


class OrgList(OrgViewNode):
    node_type = "list"

    def __init__(self, view, parent, indent):
        super(OrgList, self).__init__(view, parent)
        self.indent = indent


class OrgListEntry(OrgViewNode):
    node_type = "list_entry"

    def __init__(self, view, parent, indent, match):
        super(OrgListEntry, self).__init__(view, parent)
        self.indent = indent
        self.tick_offset = None
        if match.group("tick_box") is not None:
            self.tick_offset = match.start("tick_box") + 1


def iter_tree_depth_first(node):
    for child in node.children:
        for n in iter_tree_depth_first(child):
            yield n
    yield node


def get_folding_for_headers(view, header_region_iter):
    prev_header_end = None
    result = []
    for header_region in itertools.chain(header_region_iter, [sublime.Region(view.size() + 1, view.size() + 1)]):
        if prev_header_end is not None:
            fold_region = sublime.Region(before_line_end(view, prev_header_end), header_region.a - 1)
            assert fold_region.a <= fold_region.b
            if not fold_region.empty():
                result.append(fold_region)
        prev_header_end = header_region.b
    return result


def before_line_end(view, pos):
    if (
        0 < pos <= view.size()
        and bool(view.classify(pos - 1) & sublime.CLASS_LINE_END)
    ):
        return pos - 1
    else:
        return pos


