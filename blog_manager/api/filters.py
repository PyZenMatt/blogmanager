from django.core.exceptions import FieldError
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter


class SafeOrderingFilter(OrderingFilter):
	"""
	Evita 500 su ordering non valido restituendo 400 con dettaglio.
	"""
	def filter_queryset(self, request, queryset, view):
		ordering = self.get_ordering(request, queryset, view)
		if ordering:
			try:
				return queryset.order_by(*ordering)
			except FieldError as exc:
				# Es.: "Cannot resolve keyword 'foo' into field"
				raise ValidationError({"ordering": str(exc)})
		return queryset
