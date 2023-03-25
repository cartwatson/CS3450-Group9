from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Car, Reservation
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.http import JsonResponse
from django.utils.datastructures import MultiValueDictKeyError
import secrets


def profile(request, context=dict()):
    tabs = [
        {"url": "info",
         "tab_title": "Personal Information",
         "component_name": "Info",
         "template": 'Customer/profileTabs/personalInfo.html'},
        {"url": "balance",
         "tab_title": "Manage Balance",
         "component_name": "Balance",
         "template": 'Customer/profileTabs/manageBalance.html'},
        {"url": "reservations",
         "tab_title": "Current Reservations",
         "component_name": "Reservations",
         "template": 'Customer/profileTabs/reservations.html'},
        {"url": "pass-change",
         "tab_title": "Change Password",
         "component_name": "PassChange",
         "template": 'Customer/profileTabs/passChange.html'},
        {"url": "car-broke",
         "tab_title": "Car Broken?",
         "component_name": "CarBroken",
         "template": 'Customer/profileTabs/carBroke.html'},
    ]
    if request.user.is_authenticated:
        context.update({"tabs": tabs})
        context.update({ "password_form": PasswordChangeForm(request.user.userprofile.user) })
    else:
        context = {"error": "User is not signed in!"}
    return render(request, 'Customer/profile.html', context)

def add_balance(request):
    if request.method != "POST":
        return profile(request)
    try:
        amount = int(request.POST.get("inputBal", 0))
        if amount < 1: raise ValueError
        request.user.userprofile.balance += amount
        request.user.userprofile.full_clean()
        request.user.userprofile.save()
        context = { "bal_msg": f"Successfully added ${amount} to account!" }
    except ValueError:
        context = { "bal_msg": "Amount must be a positive integer" }
    except:
        context = {"bal_msg": "Something went wrong... Unable to transfer funds."}

    return profile(request, context=context)

def password_change(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user.userprofile.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            messages.success(request, 'Your password was successfully updated!')
        else:
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)
    return profile(request)

def search_for_res(request):
    time_now = timezone.now()
    formatedDate = time_now.strftime("%m-%d-%Y")
    car_inventory = Car.objects.all()
    context = {
        'formatedDate': formatedDate,
        'car_inventory': car_inventory,
        }
    return render(request, 'Customer/search.html', context)

def create_res(request, car_id):
    delete_expired()
    time_now = timezone.now()
    formatted_date = time_now.strftime("%m-%d-%Y")
    car = get_object_or_404(Car, pk=car_id)
    context = {
        'formatted_date': formatted_date,
        'car': car,
        'curr_reservations': Reservation.objects.filter(car=car_id),
    }
    if request.method != "POST":
        return render(request, 'Customer/reservation.html', context)

    try:
        start_date = format_date(request.POST["start-date"])
        end_date = format_date(request.POST["end-date"])
    except ValueError:
        messages.error(request, "Incorrectly formatted start or end date.")
        return render(request, 'Customer/reservation.html', context)
    except MultiValueDictKeyError:
        messages.error(request, "Incorrectly formatted start or end date.")
        return render(request, 'Customer/reservation.html', context)
    except:
        messages.error(request, "Something went wrong.")
        return render(request, 'Customer/reservation.html', context)

    if not res_available(car_id, start_date, end_date):
        messages.error(request, "Reservation not available.")
        return render(request, 'Customer/reservation.html', context)
    
    delete_unconfirmed(request.user.userprofile)
    new_reservation = Reservation.objects.create(
        car=car,
        user=request.user.userprofile,
        start_date=start_date,
        end_date=end_date,
        confirmed=False,
        processed_on=timezone.now()
    )

    token = secrets.token_urlsafe(16)
    expiration = timezone.now() + timedelta(minutes=settings.RESERVATION_EXPIRY_TIME)
    request.session['res_session'] = {
        "res_id": new_reservation.pk,
        "token": token,
        "expiration": expiration.isoformat()
    }

    new_reservation.save()
    return redirect(f'/confirm/{token}/{new_reservation.pk}')

def confirm_res(request, token, res_id):
    try:
        session_token = request.session['res_session']['token']
        session_res_id = request.session['res_session']['res_id']
        expiration = request.session['res_session']['expiration']
        expiration = datetime.fromisoformat(expiration)
        if token != session_token or expiration < timezone.now() or session_res_id != res_id:
            raise ValueError
        
        reservation = Reservation.objects.get(
            user=request.user.userprofile,
            pk=res_id,
            confirmed=False
        )
    except:
        messages.error(request, "Reservation unavailable.")
        return redirect('/search')

    if request.method == "POST":
        reservation.confirmed = True
        reservation.save()
        messages.success(request, "Successfully created reservation!")
        return redirect("/search")
    
    context = {
        "reservation": reservation,
        "car": reservation.car,
        "formatted_date": timezone.now().strftime("%m-%d-%Y"),
        "token": token,
    }
    return render(request, 'Customer/confirmation.html', context)

def availability_api(request):
    json = {}
    try:
        car_id = int(request.GET["carID"])
        start_date = format_date(request.GET["start"])
        end_date = format_date(request.GET["end"])
        car = Car.objects.get(pk=car_id)
        delta = (end_date - start_date).days + 1
        if delta <= 0:
            raise ValueError("End date cannot be before start date.")
        elif delta > 50: # Arbitrarily made this 50 days. We probably wanna change this later
            raise ValueError("Cannot reserve a car for more than 50 days.")
        price = delta * car.reservation_cost
        json['price'] = price
    except ValueError as e:
        return JsonResponse({"error": str(e)})
    except MultiValueDictKeyError:
        return JsonResponse({"error": "Request must contain parameters 'carID', 'start', and 'end'."})
    except Car.DoesNotExist:
        return JsonResponse({"error": f"Car with ID '{car_id}' does not exist."})
    except Exception as e:
        print(e)
        return JsonResponse({"error": "Something went wrong."})

    json["available"] = res_available(car, start_date, end_date)
    return JsonResponse(json)

def format_date(date: str):
    date_format = "%Y-%m-%d"
    date_obj = datetime.strptime(date, date_format).date()
    return date_obj

def res_available(car, start_date, end_date):
    delete_expired()
    overlapping = Reservation.objects.filter(
        car=car,
        end_date__gte=start_date,
        start_date__lte=end_date,
    )
    return not overlapping.exists()

def delete_expired():
    '''Delete all unconfirmed, expired reservations for every user'''
    expiration = timezone.now() - timedelta(minutes=settings.RESERVATION_EXPIRY_TIME)
    unconfirmed = Reservation.objects.filter(confirmed=False, processed_on__lte=expiration)
    unconfirmed.delete()

def delete_unconfirmed(user):
    '''Delete all unconfirmed reservations for a user'''
    unconfirmed = Reservation.objects.filter(user=user, confirmed=False)
    unconfirmed.delete()
