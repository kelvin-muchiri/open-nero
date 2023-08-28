def is_descendant(link, ancestor):
    children = ancestor.children.all()

    if not children:
        return False

    for child in children:
        if child.id == link.id:
            return True

        if is_descendant(link, child):
            return True

    return False
