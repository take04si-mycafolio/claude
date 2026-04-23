class UnicodeSlugConverter:
    """Japanese/Unicodeを含むスラッグに対応するpath converter"""

    regex = r"[^/]+"

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value
