"""Pipeline: source text -> HTML fragment."""

from .blocks import BlockParser
from .html import Renderer
from .resolve import Resolver


def render_html(text, safe=False):
    bp = BlockParser(text)
    bp.parse()
    res = Resolver(bp, safe=safe)
    res.run()
    r = Renderer(res, safe=safe)
    return r.render()
