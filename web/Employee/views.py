from django.shortcuts import render

def staff(request):
    tabs = [
        {"id": "active-rentals",
         "tab_title": "Active Rentals",
         "component_name": "ActiveRentals",
         "template": 'Employee/staffTabs/activeRentals.html' },
        {"id": "verify",
         "tab_title": "Verify Pick-Up",
         "component_name": "Verify",
         "template": 'Employee/staffTabs/verifyPickup.html' },
        {"id": "broken-cars",
         "tab_title": "Currently Broken Cars",
         "component_name": "BrokenCars",
         "template": 'Employee/staffTabs/brokenCars.html' },
    ]
    if not request.user.is_authenticated:
        context = {"error": "User is not signed in!"}
    elif request.user.userprofile.auth_level == "TW" or request.user.userprofile.auth_level == "CR":
        tabs += [
            {"id": "log-hours",
             "tab_title": "Log Hours Worked",
             "component_name": "LogHours",
             "template": 'Employee/staffTabs/logHours.html' },
            {"id": "pay-history",
             "tab_title": "Pay History",
             "component_name": "PayHistory",
             "template": 'Employee/staffTabs/payHistory.html' },
        ]
        context = {"tabs": tabs}
    elif request.user.userprofile.auth_level == "MA":
        tabs += [
            {"id": "cars",
             "tab_title": "Manage Cars",
             "component_name": "CarsView",
             "template": 'Manager/managerTabs/manageCars.html' },
            {"id": "users",
             "tab_title": "Manage Users",
             "component_name": "UsersView",
             "template": 'Manager/managerTabs/manageUsers.html' },
            {"id": "hours",
             "tab_title": "Review Hours",
             "component_name": "Hours",
             "template": 'Manager/managerTabs/reviewHours.html' },
        ]
        context = {"tabs": tabs}
    else:
        context = {"error": "User is not part of staff!"}

    return render(request, 'Employee/staff.html', context)