"""
Cancels orders that were never paid/approved within N hours and releases the stock they reserved.
Without this, abandoned checkouts would hold supplier stock forever. Run hourly (docker-compose.prod.yml's
`scheduler` service does this). Orders with a pending or successful payment are never touched.

    python manage.py expire_unpaid_orders [--hours 24]
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import Order
from orders.services import OrderError, cancel_order

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Cancel stale unpaid orders and release their reserved stock."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24)

    def handle(self, *args, **opts):
        cutoff = timezone.now() - timedelta(hours=opts["hours"])
        stale = Order.objects.filter(status__in=["draft", "submitted"], created_at__lt=cutoff)
        cancelled = skipped = 0
        for order in stale:
            try:
                cancel_order(order)
                cancelled += 1
            except OrderError as exc:  # e.g. a payment is in flight: leave it alone
                skipped += 1
                logger.info("Skipped %s: %s", order.order_number, exc)
        self.stdout.write(f"Expired {cancelled} unpaid order(s); skipped {skipped}.")
