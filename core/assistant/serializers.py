from django.conf import settings
from rest_framework import serializers


class AssistantMessageSerializer(serializers.Serializer):
    allow_ai = serializers.BooleanField(required=False, default=False)
    message = serializers.CharField(trim_whitespace=True, required=False)
    intent = serializers.CharField(required=False, max_length=64)
    arguments = serializers.DictField(required=False)
    context = serializers.DictField(required=False)
    conversation_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=False,
        max_length=64,
    )

    def validate(self, attrs):
        allowed_fields = {"message", "conversation_id", "intent", "arguments", "context", "allow_ai"}
        unknown = set(self.initial_data).difference(allowed_fields)
        if unknown:
            field = sorted(unknown)[0]
            raise serializers.ValidationError(
                {field: "Este campo no está permitido."},
                code="invalid_arguments",
            )
        if "allow_ai" in self.initial_data:
            if type(self.initial_data["allow_ai"]) is not bool or "message" not in self.initial_data:
                raise serializers.ValidationError({"allow_ai": "Envía un booleano explícito solo con message."})
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
        if "context" in attrs and not has_message:
            raise serializers.ValidationError(
                {"context": "context solo puede acompañar a message."},
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
        context = attrs.get("context")
        if context is not None:
            if set(context) != {"year", "month"}:
                raise serializers.ValidationError(
                    {"context": "El contexto solo admite year y month."},
                    code="invalid_arguments",
                )
            year = context.get("year")
            month = context.get("month")
            if isinstance(year, bool) or not isinstance(year, int) or not 1 <= year <= 9999:
                raise serializers.ValidationError(
                    {"context": {"year": "El año debe estar entre 1 y 9999."}},
                    code="invalid_arguments",
                )
            if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
                raise serializers.ValidationError(
                    {"context": {"month": "El mes debe estar entre 1 y 12."}},
                    code="invalid_arguments",
                )
        return attrs
