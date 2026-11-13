from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.assistant.errors import (
    AssistantDisabledError,
    AssistantError,
    AssistantPermissionDeniedError,
)
from core.assistant.serializers import AssistantMessageSerializer
from core.assistant.services import AssistantApplicationService
from core.models import Profile


class AssistantMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not settings.ASSISTANT_ENABLED:
            error = AssistantDisabledError()
            return Response({"error": error.to_dict()}, status=error.http_status)

        serializer = AssistantMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "error": {
                        "code": "invalid_arguments",
                        "message": "La solicitud no es válida.",
                        "details": serializer.errors,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = Profile.objects.select_related("family").filter(user=request.user).first()
        if profile is None:
            error = AssistantPermissionDeniedError()
            return Response({"error": error.to_dict()}, status=error.http_status)
        try:
            service = AssistantApplicationService()
            if "intent" in serializer.validated_data:
                data = service.process_intent(
                    actor=request.user,
                    family=profile.family,
                    intent=serializer.validated_data["intent"],
                    arguments=serializer.validated_data["arguments"],
                )
            else:
                data = service.process(
                    actor=request.user,
                    family=profile.family,
                    message=serializer.validated_data["message"],
                    context=serializer.validated_data.get("context"),
                    allow_ai=serializer.validated_data["allow_ai"],
                )
        except AssistantError as error:
            return Response({"error": error.to_dict()}, status=error.http_status)
        return Response(data, status=status.HTTP_200_OK)
