from django.db import models
from django.contrib.auth.models import User
from accounts.models import Location
from products.models import Product, SerializedItem
import random, string


def generate_grn():
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"GRN-{suffix}"

def generate_transfer_ref():
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"TRF-{suffix}"

def generate_request_ref():
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"REQ-{suffix}"


class StockLevel(models.Model):
    """Tracks quantity of non-serialized products at a location."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_levels')
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='stock_levels')
    quantity = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'location')

    def __str__(self):
        return f"{self.product.name} @ {self.location.name}: {self.quantity}"


class GoodsReceipt(models.Model):
    """Stock arriving at a warehouse from production/procurement."""
    grn_number = models.CharField(max_length=20, unique=True, default=generate_grn)
    warehouse = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='goods_receipts')
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    receipt_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.grn_number} — {self.warehouse.name}"


class GoodsReceiptItem(models.Model):
    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)  # for non-serialized
    serialized_items = models.ManyToManyField(SerializedItem, blank=True)  # for serialized

    def __str__(self):
        return f"{self.receipt.grn_number} — {self.product.name}"


class StockRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('partial', 'Partially Approved'),
        ('rejected', 'Rejected'),
        ('dispatched', 'Dispatched'),
        ('received', 'Received'),
    ]
    request_ref = models.CharField(max_length=20, unique=True, default=generate_request_ref)
    outlet = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='stock_requests',
                               limit_choices_to={'location_type': 'outlet'})
    warehouse = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='received_requests',
                                  limit_choices_to={'location_type': 'warehouse'})
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='stock_requests')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    request_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.request_ref} — {self.outlet.name} → {self.warehouse.name} [{self.get_status_display()}]"

    class Meta:
        ordering = ['-request_date']


class StockRequestItem(models.Model):
    request = models.ForeignKey(StockRequest, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_requested = models.PositiveIntegerField(default=0)
    quantity_approved = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.request.request_ref} — {self.product.name}: {self.quantity_requested} req / {self.quantity_approved} appr"


class StockTransfer(models.Model):
    STATUS_CHOICES = [
        ('dispatched', 'Dispatched'),
        ('in_transit', 'In Transit'),
        ('received', 'Received'),
        ('discrepancy', 'Discrepancy Flagged'),
    ]
    transfer_ref = models.CharField(max_length=20, unique=True, default=generate_transfer_ref)
    stock_request = models.ForeignKey(StockRequest, on_delete=models.CASCADE, related_name='transfers', null=True, blank=True)
    from_location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='outbound_transfers')
    to_location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='inbound_transfers')
    dispatched_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='dispatched_transfers')
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_transfers')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='dispatched')
    dispatch_date = models.DateTimeField(auto_now_add=True)
    receive_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    discrepancy_notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.transfer_ref}: {self.from_location.name} → {self.to_location.name}"

    class Meta:
        ordering = ['-dispatch_date']


class StockTransferItem(models.Model):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_dispatched = models.PositiveIntegerField(default=0)
    quantity_received = models.PositiveIntegerField(default=0)
    serialized_items = models.ManyToManyField(SerializedItem, blank=True)

    def __str__(self):
        return f"{self.transfer.transfer_ref} — {self.product.name}"


class WriteOff(models.Model):
    REASON_CHOICES = [
        ('damaged', 'Damaged'),
        ('lost', 'Lost'),
        ('expired', 'Expired'),
        ('stolen', 'Stolen'),
        ('other', 'Other'),
    ]
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    serialized_items = models.ManyToManyField(SerializedItem, blank=True)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='write_off_approvals')
    written_off_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='write_offs')
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Write-Off: {self.product.name} x{self.quantity} @ {self.location.name}"
