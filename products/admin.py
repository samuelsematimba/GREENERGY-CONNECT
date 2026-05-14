from django.contrib import admin
from .models import Category, Product, SerializedItem, Combo, ComboItem, LocationPrice, PriceHistory, Subsidy
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(SerializedItem)
admin.site.register(Combo)
admin.site.register(ComboItem)
admin.site.register(LocationPrice)
admin.site.register(PriceHistory)
admin.site.register(Subsidy)
