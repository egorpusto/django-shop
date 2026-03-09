import logging

from celery import shared_task

from django.core.mail import send_mail

from .models import Order

logger = logging.getLogger(__name__)


@shared_task
def order_created(order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        logger.error("order_created task: order %s not found", order_id)
        return 0
    subject = f"Order nr. {order.id}"
    message = (
        f"Dear {order.first_name},\n\n"
        f"You have successfully placed an order.\n"
        f"Your order ID is {order.id}."
    )
    mail_sent = send_mail(subject, message, "admin@myshop.com", [order.email])
    logger.info("order_created task: confirmation email sent for order %s", order_id)
    return mail_sent
