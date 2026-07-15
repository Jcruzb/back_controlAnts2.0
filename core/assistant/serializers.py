from django.conf import settings
from rest_framework import serializers


class AssistantMessageSerializer(serializers.Serializer):
    message = serializers.CharField(trim_whitespace=True, required=False)
    intent = serializers.CharField(required=False, max_length=64)
    arguments = serializers.DictField(required=False)
    conversation_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=False,
        max_length=64,
    )

    def validate(self, attrs):
        allowed_fields = {"message", "conversation_id", "intent", "arguments"}
        unknown = set(self.initial_data).difference(allowed_fields)
        if unknown:
            field = sorted(unknown)[0]
            raise serializers.ValidationError(
                {field: "Este campo no está permitido."},
                code="invalid_arguments",
            )
        has_message = "message" in attrs
        has_intent = "intent" in attrs
        if has_message == has_intent:
            raise serializers.ValidationError(
                {"message": "Envía message o intent, pero no ambos."},
                code="invalid_arguments",
            )
        if "arguments" in attrs and not has_intent:
            raise serializers.ValidationError(
                {"arguments": "arguments solo puede acompañar a intent."},
                code="invalid_arguments",
            )
        if has_intent and "arguments" not in attrs:
            raise serializers.ValidationError(
                {"arguments": "Este campo es obligatorio con intent."},
                code="invalid_arguments",
            )
        message = attrs.get("message", "")
        if len(message) > settings.ASSISTANT_MAX_MESSAGE_LENGTH:
            raise serializers.ValidationError(
                {
                    "message": (
                        "El mensaje supera el límite de "
                        f"{settings.ASSISTANT_MAX_MESSAGE_LENGTH} caracteres."
                    )
                },
                code="invalid_arguments",
            )
        return attrs
