"""file upload paths"""

from datetime import datetime


def image_path(_, filename):
    """Return path to featured image"""
    now = datetime.now()
    year = datetime.today().year
    month = datetime.today().strftime("%m")
    filename = f"{now.microsecond}-{filename}"
    return f"blog/images/{year}/{month}/{filename}"


def is_category_descendant(category, ancestor):
    """Returns True if a category is descendant of an ancestor categor, False otherwise"""
    children = ancestor.children.all()

    if not children:
        return False

    for child in children:
        if child.id == category.id:
            return True

        if is_category_descendant(category, child):
            return True

    return False
