import inspect


def autodoc_skip_protected(app, what, name, obj, skip, options):
    """
    Returns False if obj is callable and starts with _ and does not contain __ in
    its name. We want Sphinx to document our "protected" (soft private) methods.
    """
    if not skip:
        return False

    include = (
        callable(obj) and
        "__" not in name and
        name.startswith("_") and
        inspect.getdoc(obj) is not None
    )

    return not include


def setup(app):
    app.connect("autodoc-skip-member", autodoc_skip_protected)
