from django.shortcuts import get_object_or_404, redirect, render
from django.conf import settings
from django.urls import reverse
from orders.models import Order
from decimal import Decimal
import stripe

stripe.api_key = settings.STRIPE_SECRET_KEY
stripe.api_version = settings.STRIPE_API_VERSION

def payment_process(request):
    order_id = request.session.get('order_id')
    order = get_object_or_404(Order, id=order_id)

    if request.method == 'POST':
        success_url = request.build_absolute_uri(
            reverse('payment:completed')
            )
        cancel_url = request.build_absolute_uri(
            reverse('payment:canceled')
        )

        # Session data of the payment
        session_data = {
            'mode': 'payment',
            'client_reference_id': order.id,
            'success_url': success_url,
            'cancel_url': cancel_url,
            'line_items': []
        }
        # Add items to the Strope checkout session
        for item in order.items.all():
            session_data['line_items'].append(
                {
                    'price_data': {
                        'unit_amount': int(item.price * Decimal('100')),
                        'currency': 'usd',
                        'product_data': {
                            'name': item.product.name,

                        },
                    },
                    'quantity': item.quantity,
                }
            )

        # Add items to the session data
        session = stripe.checkout.Session.create(**session_data)
        # Redirect to the Stripe form
        return redirect(session.url, code=303)
    else:
        return render(request, 'payment/process.html', locals())

def payment_completed(request):
    return render(request, 'payment/completed.html')

def payment_canceled(request):
    return render(request, 'payment/canceled.html')