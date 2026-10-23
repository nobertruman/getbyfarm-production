from django.urls import path
from .views import RecommendSupplierView, OptimizeCartView

urlpatterns = [
    path("recommend/", RecommendSupplierView.as_view(), name="procurement-recommend"),
    path("optimize-cart/", OptimizeCartView.as_view(), name="procurement-optimize-cart"),
]
