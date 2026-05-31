from apps.orders.services import checkout_after, checkout_before


def checkout(data, mode):
    if mode == "before":
        return checkout_before.checkout(data)
    return checkout_after.checkout(data)
