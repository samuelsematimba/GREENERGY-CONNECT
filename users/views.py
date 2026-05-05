from django.shortcuts import render,redirect
from django.contrib.auth import authenticate,login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from GREENERGYFORMS.models import Profile

def logins(request):
    """users login authentication"""
    if request.method== "POST":
        username=request.POST.get("username")
        password=request.POST.get("password")

        user=authenticate(request, username=username,password=password)

        if user:
            login(request,user)
            return redirect("GREENERGYFORMS:index")
        return render(request, "users/login.html",{"error":"invalid credentials"})
    return render(request, "users/login.html", {'error':"invalid credentials please try again"})

def loginx(request):
    """the users login page whenever you come to the site"""
    return render(request, 'users/login.html')


@login_required
def upload_avatar(request):
    if request.method == 'POST' and request.FILES.get('avatar'):
        profile, created = Profile.objects.get_or_create(user=request.user)
        profile.avatar = request.FILES['avatar']
        profile.save()
        return JsonResponse({'url': profile.avatar.url})
    return JsonResponse({'error': 'No file'}, status=400)