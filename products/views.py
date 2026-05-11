from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Product, Category, SerializedItem, Combo, ComboItem, LocationPrice, PriceHistory
from accounts.models import Location, Country
import segno
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
import base64


@login_required
def product_list(request):
    products = Product.objects.select_related('category').filter(is_active=True)
    q = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    ptype = request.GET.get('type', '')
    if q:
        products = products.filter(name__icontains=q)
    if category_id:
        products = products.filter(category_id=category_id)
    if ptype:
        products = products.filter(product_type=ptype)
    context = {
        'products': products,
        'categories': Category.objects.all(),
        'q': q, 'category_id': category_id, 'ptype': ptype,
    }
    return render(request, 'products/product_list.html', context)


@login_required
def create_product(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        sku = request.POST.get('sku', '').strip()
        category_id = request.POST.get('category')
        product_type = request.POST.get('product_type')
        unit = request.POST.get('unit', 'piece')
        base_price = request.POST.get('base_price', 0)
        description = request.POST.get('description', '')
        image = request.FILES.get('image')
        country_ids = request.POST.getlist('countries')

        if Product.objects.filter(sku=sku).exists():
            messages.error(request, 'SKU already exists.')
        else:
            product = Product.objects.create(
                name=name, sku=sku,
                category=Category.objects.get(id=category_id) if category_id else None,
                product_type=product_type, unit=unit,
                base_price=base_price, description=description,
                image=image, created_by=request.user
            )
            if country_ids:
                product.countries.set(Country.objects.filter(id__in=country_ids))
            messages.success(request, f'Product "{name}" created.')
            return redirect('products:product_list')

    context = {
        'categories': Category.objects.all(),
        'countries': Country.objects.all(),
        'locations': Location.objects.all(),
    }
    return render(request, 'products/create_product.html', context)


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    items = product.items.all().select_related('current_location') if product.product_type == 'serialized' else None
    price_history = product.price_history.all()
    location_prices = product.location_prices.select_related('location')
    context = {
        'product': product,
        'items': items,
        'price_history': price_history,
        'location_prices': location_prices,
    }
    return render(request, 'products/product_detail.html', context)


@login_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        old_price = product.base_price
        product.name = request.POST.get('name', product.name)
        product.description = request.POST.get('description', product.description)
        product.unit = request.POST.get('unit', product.unit)
        new_price = request.POST.get('base_price')
        if new_price and float(new_price) != float(old_price):
            PriceHistory.objects.create(
                product=product, old_price=old_price,
                new_price=new_price, changed_by=request.user
            )
            product.base_price = new_price
        if request.FILES.get('image'):
            product.image = request.FILES['image']
        country_ids = request.POST.getlist('countries')
        if country_ids:
            product.countries.set(Country.objects.filter(id__in=country_ids))
        product.save()
        messages.success(request, 'Product updated.')
        return redirect('products:product_detail', pk=pk)
    context = {
        'product': product,
        'categories': Category.objects.all(),
        'countries': Country.objects.all(),
    }
    return render(request, 'products/edit_product.html', context)


@login_required
def generate_qr_for_item(request, item_pk):
    item = get_object_or_404(SerializedItem, pk=item_pk)
    if not item.qr_code:
        qr = segno.make_qr(item.serial_number, version=2)
        buffer = BytesIO()
        qr.save(buffer, kind='png', border=3, scale=15)
        buffer.seek(0)
        image = Image.open(buffer)
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype('arial.ttf', 28)
        except Exception:
            font = ImageFont.load_default()
        draw.text((100, 0), 'EMPOWER', font=font)
        draw.text((140, 425), item.serial_number, font=font)
        final = BytesIO()
        image.save(final, format='png')
        final.seek(0)
        item.qr_code.save(f"{item.serial_number}.png", ContentFile(final.read()), save=True)
        messages.success(request, f'QR code generated for {item.serial_number}')
    return redirect('products:product_detail', pk=item.product.pk)


@login_required
def add_serialized_items(request, product_pk):
    product = get_object_or_404(Product, pk=product_pk, product_type='serialized')
    if request.method == 'POST':
        serials = request.POST.get('serial_numbers', '').strip().splitlines()
        location_id = request.POST.get('location')
        location = Location.objects.filter(id=location_id).first()
        created = 0
        skipped = 0
        for s in serials:
            s = s.strip().upper()
            if s and not SerializedItem.objects.filter(serial_number=s).exists():
                SerializedItem.objects.create(product=product, serial_number=s, current_location=location)
                created += 1
            elif s:
                skipped += 1
        messages.success(request, f'{created} items added. {skipped} skipped (duplicates).')
        return redirect('products:product_detail', pk=product_pk)
    context = {'product': product, 'locations': Location.objects.all()}
    return render(request, 'products/add_serialized.html', context)


@login_required
def combo_list(request):
    combos = Combo.objects.filter(is_active=True).prefetch_related('items__product')
    return render(request, 'products/combo_list.html', {'combos': combos})


@login_required
def create_combo(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        price = request.POST.get('price', 0)
        description = request.POST.get('description', '')
        country_ids = request.POST.getlist('countries')
        product_ids = request.POST.getlist('product_ids')
        quantities = request.POST.getlist('quantities')

        combo = Combo.objects.create(
            name=name, code=code, price=price,
            description=description, created_by=request.user
        )
        if country_ids:
            combo.countries.set(Country.objects.filter(id__in=country_ids))
        for pid, qty in zip(product_ids, quantities):
            if pid and qty:
                ComboItem.objects.create(
                    combo=combo,
                    product=Product.objects.get(id=pid),
                    quantity=int(qty)
                )
        messages.success(request, f'Combo "{name}" created.')
        return redirect('products:combo_list')

    context = {
        'products': Product.objects.filter(is_active=True),
        'countries': Country.objects.all(),
    }
    return render(request, 'products/create_combo.html', context)
