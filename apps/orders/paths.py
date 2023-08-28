def path_order_item_paper(instance, filename):
    """Upload path to order item paper upload"""
    order_id = instance.order_item.order.id
    return f"orders/{order_id}/papers/{filename}"


def path_order_item_attachment(instance, filename):
    """Upload path to order item attachment upload"""
    order_id = instance.order_item.order.id
    return f"orders/{order_id}/attachments/{filename}"
