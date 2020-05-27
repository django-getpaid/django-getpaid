import swapper
from django.shortcuts import get_object_or_404
from rest_framework import permissions, views, viewsets
from rest_framework.response import Response

from getpaid.rest_framework.serializers import PaymentDetailSerializer
from getpaid.status import PaymentStatus as ps

Payment = swapper.load_model("getpaid", "Payment")
Order = swapper.load_model("getpaid", "Order")


class PaymentDetailViewSet(viewsets.GenericViewSet):
    serializer_class = PaymentDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Payment.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(order__user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        payment = self.get_object()
        if not payment.redirect_uri and payment.status == ps.NEW:
            payment.prepare_transaction(request=request, view=self)
        response_data = self.get_serializer(payment).data
        return Response(response_data)


class CallbackDetailView(views.APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk, *args, **kwargs):
        payment = get_object_or_404(Payment, pk=pk)
        return payment.handle_paywall_callback(request, *args, **kwargs)
