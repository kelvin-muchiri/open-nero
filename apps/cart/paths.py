"""Upload paths for files"""


def path_cart_item_attachment(instance, filename):
    """Upload path to cart item attachment upload"""
    cart_id = instance.cart_item.cart.id
    return f"carts/{cart_id}/attachments/{filename}"
