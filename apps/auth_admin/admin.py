from datetime import datetime

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin import helpers
from django.contrib.admin.widgets import AdminDateWidget
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.contrib.gis import admin
from django.http import HttpResponseRedirect
from django.shortcuts import render

from apps.auth_admin.tasks import create_new_customer_objects, upgrade_group
from apps.auth_admin.utils import NewCustomerData, NewUserData, UpgradeTestGroupData


class CustomUserAdmin(UserAdmin):
    actions = ["initialize_new_customer"]

    def initialize_new_customer(self, request, queryset):
        if "apply" in request.POST:
            create_new_customer_objects(
                NewCustomerData(
                    org_name=request.POST["organization_short"],
                    country_code=request.POST["country_code"],
                    date_start=datetime.fromisoformat(request.POST["id_date_start"]),
                    date_end=datetime.fromisoformat(request.POST["id_date_end"]),
                    aggregation_layer_id=request.POST["aggregationlayer"],
                    cloud_percentage=request.POST["id_date_end"],
                    use_sentinel1=request.POST.get("sentinel_1", False),
                    use_sentinel2=request.POST.get("sentinel_2", False),
                    user_ids=request.POST.get(helpers.ACTION_CHECKBOX_NAME),
                    project_name=request.POST.get("project_short", None),
                )
            )
            messages.info(
                request,
                f"Request to start a group for {request.POST['organization_short']} registered",
            )
            return HttpResponseRedirect(request.get_full_path())

        date_form = AdminDateWidget()

        return render(
            request,
            "initialize_customer.html",
            context={
                "user": queryset,
                "title": "Initialize new Customer",
                "site_header": "Tesselo Admin",
                "media": self.media,
                "queryset": queryset,
                "date_form": date_form,
                "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            },
        )

    initialize_new_customer.short_description = "Initialize new customer"


class CustomGroupAdmin(GroupAdmin):
    actions = ["upgrade_test_group"]

    @property
    def media(self):
        extra = "" if settings.DEBUG else ".min"
        js = [
            "vendor/jquery/jquery%s.js" % extra,
            "jquery.init.js",
            "core.js",
            "admin/RelatedObjectLookups.js",
            "actions%s.js" % extra,
            "change_form.js",
            "inlines.js",
            "urlify.js",
            "prepopulate%s.js" % extra,
            "prepopulate_init.js",
            "vendor/xregexp/xregexp%s.js" % extra,
        ]
        return forms.Media(js=["admin/js/%s" % url for url in js])

    def upgrade_test_group(self, request, queryset):
        if len(queryset) > 1:
            messages.error(request, "Group upgrades just one by one, please")
            return HttpResponseRedirect(request.get_full_path())
        group = queryset[0]

        if "TEST" not in group.name:
            messages.error(request, "That was not a test group, aborting mission")
            return HttpResponseRedirect(request.get_full_path())

        if "apply" in request.POST:
            users_data = []
            for i in range(int(request.POST["user_set-TOTAL_FORMS"])):
                prefix = f"user_set-{i}-"
                users_data.append(
                    NewUserData(
                        first_name=request.POST[f"{prefix}first-name"],
                        last_name=request.POST[f"{prefix}last-name"],
                        email=request.POST[f"{prefix}email"],
                        create_token=request.POST.get(f"{prefix}token", False),
                        language=request.POST[f"{prefix}language"],
                    )
                )
            upgrade_group(
                UpgradeTestGroupData(test_group_id=group.pk, users_data=users_data)
            )
            messages.info(
                request,
                f"Request to upgrade the group {group.name} registered",
            )
            return HttpResponseRedirect(request.get_full_path())

        return render(
            request,
            "upgrade_group.html",
            context={
                "group": group,
                "title": "Upgrade test Group",
                "site_header": "Tesselo Admin",
                "media": self.media,
                "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            },
        )

    upgrade_test_group.short_description = "Upgrade to Production Group"


admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
