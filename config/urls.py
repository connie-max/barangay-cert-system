from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from certificates import views as certificates_views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='certificates/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('signup/', certificates_views.signup, name='signup'),
    path('', certificates_views.home, name='home'),
    path('request/', certificates_views.request_certificate, name='request_certificate'),
    path('my-requests/', certificates_views.my_requests, name='my_requests'),
    path('manage-requests/', certificates_views.manage_requests, name='manage_requests'),
    path('manage-requests/<int:request_id>/mark-paid/', certificates_views.mark_as_paid, name='mark_as_paid'),
    path('manage-requests/<int:request_id>/mark-ready/', certificates_views.mark_ready_for_pickup, name='mark_ready_for_pickup'),
    path('manage-requests/<int:request_id>/<str:new_status>/', certificates_views.update_request_status, name='update_request_status'),
    path('my-requests/<int:request_id>/cancel/', certificates_views.cancel_request, name='cancel_request'),
    path('my-requests/<int:request_id>/pay/', certificates_views.submit_payment_reference, name='submit_payment_reference'),
    path('pending-accounts/', certificates_views.pending_accounts, name='pending_accounts'),
    path('pending-accounts/<int:user_id>/approve/', certificates_views.approve_account, name='approve_account'),
    path('pending-accounts/<int:user_id>/reject/', certificates_views.reject_account, name='reject_account'),
            path('residents/', certificates_views.residents_list, name='residents_list'),
    # Staff-only report of recorded payments (OR numbers) to pass to the higher-ups.
    path('collections-report/', certificates_views.collections_report, name='collections_report'),
    path('collections-report/download.xlsx', certificates_views.collections_report_xlsx, name='collections_report_xlsx'),
    path('collections-report/download.pdf', certificates_views.collections_report_pdf, name='collections_report_pdf'),
    # Private uploaded photos: staff (or the uploader) only. There is no public /media/ route.
    path('attachments/<int:attachment_id>/', certificates_views.attachment_image, name='attachment_image'),
]