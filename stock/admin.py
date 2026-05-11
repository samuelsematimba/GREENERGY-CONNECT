from django.contrib import admin
from .models import StockLevel, GoodsReceipt, GoodsReceiptItem, StockRequest, StockRequestItem, StockTransfer, StockTransferItem, WriteOff
admin.site.register(StockLevel)
admin.site.register(GoodsReceipt)
admin.site.register(GoodsReceiptItem)
admin.site.register(StockRequest)
admin.site.register(StockRequestItem)
admin.site.register(StockTransfer)
admin.site.register(StockTransferItem)
admin.site.register(WriteOff)
