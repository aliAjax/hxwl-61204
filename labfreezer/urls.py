from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("samples/", views.samples),
    path("samples/<int:sample_id>/move/", views.move_sample),
    path("samples/<int:sample_id>/checkout/", views.checkout_sample),
    path("slots/", views.slots),
    path("owners/<str:owner>/samples/", views.owner_samples),
]
